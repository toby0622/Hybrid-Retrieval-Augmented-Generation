# HRAG Frontend

The frontend for the **DevOps Incident Response Copilot**, built with **Next.js 16**, **Tailwind CSS**, and **React 19**.

## 🚀 Features

- **Incident Copilot**: Chat interface with streaming reasoning steps and diagnostic cards.
- **Knowledge Base**: Drag-and-drop ingestion of logs and docs.
- **Gardener Interface**: Human-in-the-Loop review for entity conflicts.
- **Dynamic UI**: Responsive design with dark mode, glassmorphism, and animations.

## 🛠️ Prerequisites

- **Node.js 20+**
- **npm** or **yarn**

## 📦 Installation

1.  Navigate to the frontend directory:
    ```bash
    cd hrag-frontend
    ```

2.  Install dependencies:
    ```bash
    npm install
    ```

3.  Set up environment variables:
    Create a `.env.local` file in the `hrag-frontend` directory:
    ```env
    NEXT_PUBLIC_API_URL=http://localhost:8000
    ```

## 🏃 Running the Application

Start the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## 🏗️ Project Structure

- `app/`: Next.js App Router pages (`page.tsx`, `layout.tsx`).
- `components/`: Reusable React components.
    - `copilot/`: Chat-related components (`chat-interface`, `diagnostic-card`, `dynamic-reasoning`).
    - `knowledge/`: Knowledge base components (`knowledge-interface`, `entity-card`, `upload-zone`).
    - `ui/`: Generic UI components (shadcn/ui style).
- `lib/`: Utilities and API client (`api.ts`).
- `types/`: TypeScript interfaces.
