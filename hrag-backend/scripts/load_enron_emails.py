"""
Enron Email Dataset Loader

Parses Enron email files and populates Neo4j graph database and Qdrant vector database.
Uses the ontology schema defined in enron_schema.py for consistent entity/relation creation.

Usage:
    python scripts/load_enron_emails.py --limit 500
    python scripts/load_enron_emails.py --limit 1000 --users 10
"""

import argparse
import asyncio
import email
import os
import random
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
from neo4j import AsyncGraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

# Load environment variables
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Import schema definitions
from enron_schema import EntityType, RelationType, get_schema_for_llm_prompt

# =============================================================================
# Configuration
# =============================================================================

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "hrag_documents")

LM_STUDIO_URL = os.getenv("LLM_BASE_URL", "http://localhost:8192/v1")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-embeddinggemma-300m")
EMBEDDING_DIM = 768

# Dataset path (relative to script location)
SCRIPT_DIR = Path(__file__).parent
DATASET_PATH = SCRIPT_DIR / "enron_mail_dataset"

# Check if running on Windows
IS_WINDOWS = os.name == 'nt'


# =============================================================================
# Windows File Reading Helper (for trailing-period filenames)
# =============================================================================


def read_file_content(file_path: Path) -> str:
    """
    Read file content with Windows compatibility for trailing-period filenames.
    Windows strips trailing periods from paths, so we use Win32 API on Windows.
    """
    if not IS_WINDOWS:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    
    # Use Win32 API with extended path prefix to bypass path normalization
    import ctypes
    from ctypes import wintypes
    
    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x00000001
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 0x80
    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
    
    kernel32 = ctypes.windll.kernel32
    
    # Create extended path with \\?\ prefix
    abs_path = os.path.abspath(str(file_path))
    extended_path = '\\\\?\\' + abs_path
    
    # CreateFileW
    handle = kernel32.CreateFileW(
        extended_path,
        GENERIC_READ,
        FILE_SHARE_READ,
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None
    )
    
    if handle == INVALID_HANDLE_VALUE:
        raise FileNotFoundError(f"Cannot open file: {file_path}")
    
    try:
        # Get file size
        size = kernel32.GetFileSize(handle, None)
        if size <= 0:
            return ""
        
        # Read file
        buffer = ctypes.create_string_buffer(size + 1)
        bytes_read = wintypes.DWORD()
        result = kernel32.ReadFile(handle, buffer, size, ctypes.byref(bytes_read), None)
        
        if not result:
            raise IOError(f"Failed to read file: {file_path}")
        
        return buffer.value.decode('utf-8', errors='ignore')
    finally:
        kernel32.CloseHandle(handle)


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class ParsedEmail:
    """Parsed email message with extracted metadata."""

    message_id: str
    date: Optional[datetime]
    date_str: str
    from_email: str
    from_name: str
    to_emails: List[str]
    to_names: List[str]
    cc_emails: List[str]
    cc_names: List[str]
    bcc_emails: List[str]
    subject: str
    body: str
    folder: str
    origin: str
    filename: str
    attachments: List[str]
    is_reply: bool
    is_forward: bool
    file_path: str

    @property
    def content_for_embedding(self) -> str:
        """Get content suitable for embedding generation."""
        parts = []
        if self.subject:
            parts.append(f"Subject: {self.subject}")
        if self.from_name:
            parts.append(f"From: {self.from_name}")
        if self.to_names:
            parts.append(f"To: {', '.join(self.to_names[:3])}")
        if self.body:
            # Truncate body to reasonable length for embedding
            body_preview = self.body[:2000]
            parts.append(body_preview)
        return "\n".join(parts)


# =============================================================================
# Email Parsing
# =============================================================================


def parse_email_file(file_path: Path) -> Optional[ParsedEmail]:
    """Parse a single Enron email file."""
    try:
        content = read_file_content(file_path)

        # Parse headers and body
        headers = {}
        lines = content.split("\n")
        body_start = 0

        current_header = None
        current_value = []

        for i, line in enumerate(lines):
            # Empty line marks end of headers
            if line.strip() == "":
                body_start = i + 1
                # Save last header
                if current_header:
                    headers[current_header] = " ".join(current_value).strip()
                break

            # Continuation of previous header (starts with whitespace)
            if line.startswith((" ", "\t")) and current_header:
                current_value.append(line.strip())
            else:
                # Save previous header
                if current_header:
                    headers[current_header] = " ".join(current_value).strip()

                # Parse new header
                if ":" in line:
                    key, _, value = line.partition(":")
                    current_header = key.strip()
                    current_value = [value.strip()]
                else:
                    current_header = None
                    current_value = []

        body = "\n".join(lines[body_start:]).strip()

        # Extract email addresses and names
        def parse_email_list(header_value: str) -> Tuple[List[str], List[str]]:
            """Parse email addresses and names from header."""
            emails = []
            names = []
            if not header_value:
                return emails, names

            # Handle multiple recipients separated by commas
            for part in header_value.split(","):
                part = part.strip()
                # Try to extract email
                email_match = re.search(r"[\w\.-]+@[\w\.-]+", part)
                if email_match:
                    emails.append(email_match.group().lower())
                # Try to extract name
                name = re.sub(r"<[^>]+>", "", part).strip()
                name = re.sub(r"[\w\.-]+@[\w\.-]+", "", name).strip()
                name = name.strip("\"'<>() \t")
                if name:
                    names.append(name)
                elif email_match:
                    # Use email prefix as name fallback
                    names.append(email_match.group().split("@")[0])

            return emails, names

        # Parse From
        from_emails, from_names = parse_email_list(headers.get("From", ""))
        from_email = from_emails[0] if from_emails else ""
        from_name = from_names[0] if from_names else headers.get("X-From", "").strip()

        # Parse To
        to_emails, to_names = parse_email_list(headers.get("To", ""))
        if not to_names and headers.get("X-To"):
            to_names = [n.strip() for n in headers.get("X-To", "").split(",") if n.strip()]

        # Parse CC
        cc_emails, cc_names = parse_email_list(headers.get("X-cc", ""))

        # Parse BCC
        bcc_emails, _ = parse_email_list(headers.get("X-bcc", ""))

        # Parse date
        date_str = headers.get("Date", "")
        parsed_date = None
        if date_str:
            try:
                # Try common Enron date formats
                for fmt in [
                    "%a, %d %b %Y %H:%M:%S %z",
                    "%a, %d %b %Y %H:%M:%S %Z",
                    "%d %b %Y %H:%M:%S %z",
                ]:
                    try:
                        # Remove timezone abbreviation in parentheses
                        clean_date = re.sub(r"\s*\([^)]+\)", "", date_str)
                        parsed_date = datetime.strptime(clean_date.strip(), fmt)
                        break
                    except ValueError:
                        continue
            except Exception:
                pass

        # Check for attachments
        attachments = re.findall(r"<<\s*File:\s*([^>]+)\s*>>", body)

        # Determine if reply or forward
        subject = headers.get("Subject", "").strip()
        is_reply = subject.lower().startswith("re:")
        is_forward = subject.lower().startswith(("fw:", "fwd:"))

        return ParsedEmail(
            message_id=headers.get("Message-ID", f"gen-{hash(content)}").strip("<>"),
            date=parsed_date,
            date_str=date_str,
            from_email=from_email,
            from_name=from_name,
            to_emails=to_emails,
            to_names=to_names,
            cc_emails=cc_emails,
            cc_names=cc_names,
            bcc_emails=bcc_emails,
            subject=subject,
            body=body,
            folder=headers.get("X-Folder", "").strip(),
            origin=headers.get("X-Origin", "").strip(),
            filename=headers.get("X-FileName", "").strip(),
            attachments=attachments,
            is_reply=is_reply,
            is_forward=is_forward,
            file_path=str(file_path),
        )

    except Exception as e:
        print(f"      [WARN] Error parsing {file_path}: {e}")
        return None


def collect_email_files(
    dataset_path: Path, max_emails: int = 0
) -> List[Path]:
    """
    Collect all email file paths from the dataset.
    Uses os.scandir for Windows compatibility with trailing-period filenames.
    
    Args:
        dataset_path: Path to the enron_mail_dataset directory
        max_emails: Maximum emails to load (0 = no limit)
    """
    print(f"[DIR] Scanning dataset at {dataset_path}...")

    valid_files = []
    users_found = 0
    
    # Scan each user directory
    try:
        for user_entry in os.scandir(str(dataset_path)):
            if not user_entry.is_dir():
                continue
            users_found += 1
            
            # Scan each folder in user directory
            try:
                for folder_entry in os.scandir(user_entry.path):
                    if not folder_entry.is_dir():
                        continue
                    
                    # Scan email files in folder
                    try:
                        for email_entry in os.scandir(folder_entry.path):
                            if not email_entry.is_file():
                                continue
                            try:
                                size = email_entry.stat().st_size
                                # Skip very large files (newsletters) and very small files
                                if 100 <= size <= 50000:
                                    valid_files.append(Path(email_entry.path))
                            except OSError:
                                continue
                    except (PermissionError, OSError):
                        continue
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError) as e:
        print(f"   [ERROR] Cannot scan dataset: {e}")
        return []

    print(f"   Found {users_found} user mailboxes")
    print(f"   Valid email files (100B-50KB): {len(valid_files)}")

    # Apply limit if specified
    if max_emails > 0 and len(valid_files) > max_emails:
        # Take evenly distributed sample
        step = len(valid_files) // max_emails
        selected = valid_files[::step][:max_emails]
        print(f"   Selected {len(selected)} emails (limit: {max_emails})")
        return selected

    print(f"   Loading all {len(valid_files)} emails")
    return valid_files


# =============================================================================
# Embedding Generation
# =============================================================================


def get_embedding(text: str, use_lm_studio: bool = True) -> List[float]:
    """Get embedding from LM Studio or fallback to random."""
    if use_lm_studio:
        try:
            import httpx

            response = httpx.post(
                f"{LM_STUDIO_URL}/embeddings",
                json={"model": EMBEDDING_MODEL, "input": text[:8000]},  # Truncate
                headers={"Authorization": "Bearer lm-studio"},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()["data"][0]["embedding"]
        except Exception as e:
            print(f"      LM Studio embedding failed: {e}, using fallback")

    # Fallback to deterministic random embedding
    content_hash = hash(text) % 10000
    np.random.seed(content_hash)
    embedding = np.random.randn(EMBEDDING_DIM).astype(np.float32)
    return (embedding / np.linalg.norm(embedding)).tolist()


# =============================================================================
# Neo4j Database Population
# =============================================================================


async def init_neo4j(emails: List[ParsedEmail]):
    """Initialize Neo4j with email data following the ontology schema."""
    print("\n[NEO4J] Connecting to Neo4j...")

    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    async with driver.session() as session:
        # Clear existing data
        print("   Clearing existing data...")
        await session.run("MATCH (n) DETACH DELETE n")

        # Create indexes for better performance
        print("   Creating indexes...")
        await session.run(
            "CREATE INDEX IF NOT EXISTS FOR (p:Person) ON (p.email)"
        )
        await session.run(
            "CREATE INDEX IF NOT EXISTS FOR (e:Email) ON (e.message_id)"
        )
        await session.run(
            "CREATE INDEX IF NOT EXISTS FOR (o:Organization) ON (o.name)"
        )

        # Track created entities
        created_persons: Set[str] = set()
        created_orgs: Set[str] = set()

        print(f"   Creating nodes and relationships for {len(emails)} emails...")

        for i, email_data in enumerate(emails):
            if (i + 1) % 50 == 0:
                print(f"      [{i+1}/{len(emails)}] Processing...")

            # Create Email node
            await session.run(
                """
                CREATE (e:Email {
                    message_id: $message_id,
                    subject: $subject,
                    date: $date,
                    folder: $folder,
                    content_preview: $preview,
                    has_attachment: $has_attachment,
                    is_reply: $is_reply,
                    is_forward: $is_forward,
                    file_path: $file_path
                })
                """,
                message_id=email_data.message_id,
                subject=email_data.subject,
                date=email_data.date_str,
                folder=email_data.folder,
                preview=email_data.body[:500] if email_data.body else "",
                has_attachment=len(email_data.attachments) > 0,
                is_reply=email_data.is_reply,
                is_forward=email_data.is_forward,
                file_path=email_data.file_path,
            )

            # Create sender Person node and SENT_BY relationship
            if email_data.from_email:
                if email_data.from_email not in created_persons:
                    # Extract organization from email domain
                    domain = email_data.from_email.split("@")[-1] if "@" in email_data.from_email else ""
                    org_name = domain.split(".")[0].title() if domain else "Unknown"

                    await session.run(
                        """
                        MERGE (p:Person {email: $email})
                        ON CREATE SET p.name = $name, p.domain = $domain
                        """,
                        email=email_data.from_email,
                        name=email_data.from_name or email_data.from_email.split("@")[0],
                        domain=domain,
                    )
                    created_persons.add(email_data.from_email)

                    # Create Organization and WORKS_AT if it's an Enron email
                    if "enron" in domain.lower() and org_name not in created_orgs:
                        await session.run(
                            """
                            MERGE (o:Organization {name: $name})
                            ON CREATE SET o.type = 'Company', o.domain = $domain
                            """,
                            name="Enron",
                            domain="enron.com",
                        )
                        created_orgs.add("Enron")

                        await session.run(
                            """
                            MATCH (p:Person {email: $email})
                            MATCH (o:Organization {name: 'Enron'})
                            MERGE (p)-[:WORKS_AT]->(o)
                            """,
                            email=email_data.from_email,
                        )

                # Create SENT_BY relationship
                await session.run(
                    """
                    MATCH (e:Email {message_id: $message_id})
                    MATCH (p:Person {email: $email})
                    CREATE (e)-[:SENT_BY {timestamp: $date}]->(p)
                    """,
                    message_id=email_data.message_id,
                    email=email_data.from_email,
                    date=email_data.date_str,
                )

            # Create recipient Person nodes and SENT_TO relationships
            for j, to_email in enumerate(email_data.to_emails[:10]):  # Limit recipients
                if to_email not in created_persons:
                    to_name = email_data.to_names[j] if j < len(email_data.to_names) else to_email.split("@")[0]
                    domain = to_email.split("@")[-1] if "@" in to_email else ""

                    await session.run(
                        """
                        MERGE (p:Person {email: $email})
                        ON CREATE SET p.name = $name, p.domain = $domain
                        """,
                        email=to_email,
                        name=to_name,
                        domain=domain,
                    )
                    created_persons.add(to_email)

                await session.run(
                    """
                    MATCH (e:Email {message_id: $message_id})
                    MATCH (p:Person {email: $email})
                    MERGE (e)-[:SENT_TO {timestamp: $date}]->(p)
                    """,
                    message_id=email_data.message_id,
                    email=to_email,
                    date=email_data.date_str,
                )

            # Create CC relationships
            for cc_email in email_data.cc_emails[:5]:  # Limit CC
                if cc_email not in created_persons:
                    await session.run(
                        """
                        MERGE (p:Person {email: $email})
                        ON CREATE SET p.name = $name
                        """,
                        email=cc_email,
                        name=cc_email.split("@")[0],
                    )
                    created_persons.add(cc_email)

                await session.run(
                    """
                    MATCH (e:Email {message_id: $message_id})
                    MATCH (p:Person {email: $email})
                    MERGE (e)-[:CC_TO]->(p)
                    """,
                    message_id=email_data.message_id,
                    email=cc_email,
                )

            # Create Document nodes for attachments
            for attachment in email_data.attachments:
                await session.run(
                    """
                    MATCH (e:Email {message_id: $message_id})
                    MERGE (d:Document {filename: $filename})
                    ON CREATE SET d.type = $type
                    CREATE (e)-[:HAS_ATTACHMENT]->(d)
                    """,
                    message_id=email_data.message_id,
                    filename=attachment.strip(),
                    type=attachment.split(".")[-1] if "." in attachment else "unknown",
                )

        print("   [OK] Neo4j initialized successfully!")

        # Print summary
        result = await session.run(
            "MATCH (n) RETURN labels(n)[0] as label, count(*) as count ORDER BY count DESC"
        )
        records = await result.data()
        for record in records:
            print(f"      - {record['label']}: {record['count']} nodes")

        result = await session.run(
            "MATCH ()-[r]->() RETURN type(r) as type, count(*) as count ORDER BY count DESC"
        )
        records = await result.data()
        for record in records:
            print(f"      - {record['type']}: {record['count']} relationships")

    await driver.close()


# =============================================================================
# Qdrant Database Population
# =============================================================================


def init_qdrant(emails: List[ParsedEmail], use_lm_studio: bool = True):
    """Initialize Qdrant with email embeddings."""
    print("\n[QDRANT] Connecting to Qdrant...")

    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    # Delete collection if exists
    try:
        client.delete_collection(QDRANT_COLLECTION)
        print("   Deleted existing collection")
    except Exception:
        pass

    # Create collection
    print(f"   Creating collection '{QDRANT_COLLECTION}'...")
    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )

    # Generate embeddings and create points
    mode = "LM Studio" if use_lm_studio else "random fallback"
    print(f"   Generating embeddings ({mode})...")

    points = []
    for i, email_data in enumerate(emails):
        if (i + 1) % 50 == 0:
            print(f"      [{i+1}/{len(emails)}] Generating embeddings...")

        content = email_data.content_for_embedding
        if not content.strip():
            continue

        embedding = get_embedding(content, use_lm_studio)

        points.append(
            PointStruct(
                id=i + 1,
                vector=embedding,
                payload={
                    "message_id": email_data.message_id,
                    "title": email_data.subject or "(No Subject)",
                    "content": email_data.body[:2000] if email_data.body else "",
                    "document_type": "email",
                    "from_email": email_data.from_email,
                    "from_name": email_data.from_name,
                    "to_emails": email_data.to_emails[:5],
                    "date": email_data.date_str,
                    "folder": email_data.folder,
                    "has_attachment": len(email_data.attachments) > 0,
                    "is_reply": email_data.is_reply,
                    "is_forward": email_data.is_forward,
                    "tags": [],
                },
            )
        )

    # Batch upsert
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        client.upsert(collection_name=QDRANT_COLLECTION, points=batch)

    print(f"   [OK] Qdrant initialized with {len(points)} documents!")

    # Verify
    collection_info = client.get_collection(QDRANT_COLLECTION)
    print(f"      - Collection: {QDRANT_COLLECTION}")
    print(f"      - Points: {collection_info.points_count}")


# =============================================================================
# Main Entry Point
# =============================================================================


async def main():
    parser = argparse.ArgumentParser(
        description="Load Enron email dataset into Neo4j and Qdrant"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Maximum number of emails to load (default: 500)",
    )
    parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Skip LM Studio embeddings, use random fallback",
    )
    parser.add_argument(
        "--skip-neo4j",
        action="store_true",
        help="Skip Neo4j initialization",
    )
    parser.add_argument(
        "--skip-qdrant",
        action="store_true",
        help="Skip Qdrant initialization",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Enron Email Dataset Loader")
    print("=" * 60)
    print(f"Dataset path: {DATASET_PATH}")
    print(f"Email limit: {args.limit}")
    print()

    # Check dataset exists
    if not DATASET_PATH.exists():
        print(f"[ERROR] Dataset not found at {DATASET_PATH}")
        print("   Please ensure the enron_mail_dataset folder exists.")
        return

    # Collect and parse emails
    email_files = collect_email_files(
        DATASET_PATH, max_emails=args.limit
    )

    print(f"\n[MAIL] Parsing {len(email_files)} email files...")
    parsed_emails = []
    for i, file_path in enumerate(email_files):
        if (i + 1) % 100 == 0:
            print(f"   [{i+1}/{len(email_files)}] Parsing...")

        email_data = parse_email_file(file_path)
        if email_data:
            parsed_emails.append(email_data)

    print(f"   Successfully parsed {len(parsed_emails)} emails")

    # Initialize databases
    if not args.skip_neo4j:
        try:
            await init_neo4j(parsed_emails)
        except Exception as e:
            print(f"   [ERROR] Neo4j initialization failed: {e}")

    if not args.skip_qdrant:
        try:
            init_qdrant(parsed_emails, use_lm_studio=not args.no_embeddings)
        except Exception as e:
            print(f"   [ERROR] Qdrant initialization failed: {e}")

    print("\n" + "=" * 60)
    print("Initialization complete!")
    print("=" * 60)

    # Print schema info
    print("\n[SCHEMA] Using ontology schema with:")
    print("   Entity types: Person, Email, Organization, Document")
    print("   Relation types: SENT_BY, SENT_TO, CC_TO, WORKS_AT, HAS_ATTACHMENT")
    print("\n   For full schema, run: python scripts/enron_schema.py")


if __name__ == "__main__":
    asyncio.run(main())
