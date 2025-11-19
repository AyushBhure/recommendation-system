# Recommendation System Frontend

React demo application for the recommendation system.

## Development

```bash
# Install dependencies
npm install

# Start development server
npm start
```

The app will be available at http://localhost:3000

## Environment Variables

- `REACT_APP_INGEST_API`: Ingestion service URL (default: http://localhost:8000)
- `REACT_APP_SERVE_API`: Serving service URL (default: http://localhost:8001)

## Production Build

```bash
npm run build
```

## Docker

```bash
docker build -t recommendation-frontend .
docker run -p 3000:80 recommendation-frontend
```

