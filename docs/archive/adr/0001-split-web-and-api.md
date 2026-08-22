# Use a React frontend and FastAPI modular monolith

The product uses a React and TypeScript browser application with a separate FastAPI modular monolith backed by PostgreSQL.
This makes the backend engineering and workflow interface explicit while keeping financial rules in pure Python domain modules rather than in HTTP handlers, SQLAlchemy models, or UI code.
Docker Compose provides one reviewer command without introducing microservices, queues, or a second server-side web framework.
