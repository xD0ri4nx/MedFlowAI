# MedFlowAI

Medical AI Flow Management System - A FastAPI-based backend service for medical workflow automation and AI integration.

## Project Structure

```
├── app/                       # Main application package
│   ├── __init__.py
│   ├── main.py                # FastAPI app with all routes
│   └── services/              # Empty folder for future business logic
│       └── __init__.py
├── config.py                  # Pydantic Settings configuration
├── main.py                    # Entry point for running the server
├── .env                       # Environment variables (not in git)
├── .env.example               # Example environment variables
├── requirements.txt           # Python dependencies
└── .gitignore                 # Git ignore rules
```

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd MedFlowAI
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process # If not configured for Windows
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

## Running the Server

### Option 1: Using the entry point script
```bash
python main.py
```

### Option 2: Using uvicorn directly
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 3: Using uvicorn with custom settings
```bash
# Development mode with auto-reload
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --log-level info

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

The server will start at `http://localhost:8000`

## API Documentation

Once the server is running, you can access:

- **Interactive API docs (Swagger UI)**: http://localhost:8000/docs
- **Alternative API docs (ReDoc)**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Available Endpoints

- `GET /` - Root endpoint, returns welcome message
- `GET /health` - Health check endpoint
- `GET /api/v1/status` - API status with version info

## Configuration

Configuration is managed through environment variables using Pydantic Settings.
Edit the `.env` file to customize:

- `APP_NAME` - Application name
- `ENVIRONMENT` - Environment (development/staging/production)
- `DEBUG` - Debug mode (True/False)
- `HOST` - Server host (default: 0.0.0.0)
- `PORT` - Server port (default: 8000)
- `ALLOWED_ORIGINS` - CORS allowed origins
- `DATABASE_URL` - Database connection string
- `OPENAI_API_KEY` - OpenAI API key for AI features

## Development

### Project Features

- FastAPI framework for high-performance API development
- Pydantic Settings for configuration management
- CORS middleware pre-configured
- Modular structure ready for scaling
- Environment-based configuration
- Auto-generated API documentation

### Adding New Routes

Add new endpoints in `app/main.py` or create separate route files in the `app/` directory.

### Adding Business Logic

Place business logic and services in the `app/services/` directory.

## Tech Stack

- **FastAPI** - Modern, fast web framework
- **Uvicorn** - ASGI server implementation
- **Pydantic** - Data validation using Python type hints
- **SQLAlchemy** - SQL toolkit (for future database integration)
- **OpenAI** - AI integration capabilities (for future features)

## License

[Add your license here]

## Contributing

[Add contributing guidelines here]