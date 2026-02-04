
from typing import Any, Dict, List, Optional

import asyncpg

from app.core.config import settings


class MCPDatabaseClient:
    
    _pool: Optional[asyncpg.Pool] = None
    
    @classmethod
    async def get_pool(cls) -> Optional[asyncpg.Pool]:
        if cls._pool is None:
            try:
                cls._pool = await asyncpg.create_pool(
                    host=settings.mcp_db_host,
                    port=settings.mcp_db_port,
                    database=settings.mcp_db_name,
                    user=settings.mcp_db_user,
                    password=settings.mcp_db_password,
                    min_size=1,
                    max_size=5,
                )
            except Exception as e:
                print(f"[MCP] Failed to connect to PostgreSQL: {e}")
                cls._pool = None
        return cls._pool
    
    @classmethod
    async def close(cls) -> None:
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
    
    @classmethod
    async def is_available(cls) -> bool:
        if not settings.mcp_enabled:
            return False
        pool = await cls.get_pool()
        return pool is not None
    
    @classmethod
    async def execute_query(
        cls, 
        query: str, 
        params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        pool = await cls.get_pool()
        if not pool:
            return []
        
        try:
            async with pool.acquire() as conn:
                if params:
                    rows = await conn.fetch(query, *params)
                else:
                    rows = await conn.fetch(query)
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"[MCP] Query error: {e}")
            return []


class MCPTools:
    
    @staticmethod
    async def query_service_metrics(
        service_name: str,
        limit: int = 10
    ) -> tuple[List[Dict[str, Any]], str]:
        query = """
            SELECT 
                service_name,
                metric_name,
                metric_value,
                unit,
                timestamp
            FROM service_metrics
            WHERE LOWER(service_name) LIKE LOWER($1)
            ORDER BY timestamp DESC
            LIMIT $2
        """
        results = await MCPDatabaseClient.execute_query(
            query, (f"%{service_name}%", limit)
        )
        return results, query.strip()
    
    @staticmethod
    async def query_service_logs(
        service_name: Optional[str] = None,
        log_level: Optional[str] = None,
        limit: int = 10
    ) -> tuple[List[Dict[str, Any]], str]:
        conditions = []
        params = []
        param_idx = 1
        
        if service_name:
            conditions.append(f"LOWER(service_name) LIKE LOWER(${param_idx})")
            params.append(f"%{service_name}%")
            param_idx += 1
        
        if log_level:
            conditions.append(f"LOWER(log_level) = LOWER(${param_idx})")
            params.append(log_level)
            param_idx += 1
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)
        
        query = f"""
            SELECT 
                service_name,
                log_level,
                message,
                timestamp
            FROM service_logs
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ${param_idx}
        """
        results = await MCPDatabaseClient.execute_query(query, tuple(params))
        return results, query.strip()
    
    @staticmethod
    async def get_service_health(
        service_name: str
    ) -> tuple[List[Dict[str, Any]], str]:
        query = """
            SELECT 
                service_name,
                health_status,
                last_check,
                details
            FROM service_health
            WHERE LOWER(service_name) LIKE LOWER($1)
            ORDER BY last_check DESC
            LIMIT 1
        """
        results = await MCPDatabaseClient.execute_query(
            query, (f"%{service_name}%",)
        )
        return results, query.strip()
    
    @staticmethod
    async def query_realtime_data(
        table_name: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20
    ) -> tuple[List[Dict[str, Any]], str]:
        allowed_tables = [
            "service_metrics",
            "service_logs", 
            "service_health",
            "realtime_data"
        ]
        
        if table_name not in allowed_tables:
            return [], ""
        
        conditions = []
        params = []
        param_idx = 1
        
        if filters:
            for col, val in filters.items():
                if col.replace("_", "").isalnum():
                    conditions.append(f"{col} = ${param_idx}")
                    params.append(val)
                    param_idx += 1
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)
        
        query = f"""
            SELECT * FROM {table_name}
            WHERE {where_clause}
            ORDER BY 1 DESC
            LIMIT ${param_idx}
        """
        
        try:
            results = await MCPDatabaseClient.execute_query(query, tuple(params))
            return results, query.strip()
        except Exception:
            return [], query.strip()
