# image-sift-search

## Running the Application

### Start the Web and Qdrant Services
To start the main application (the web server and Qdrant database):

```bash
docker compose up -d
```

### Running the Data Ingestion Pipeline (`ingest.py`)

The `ingest` service is assigned to a specific Docker Compose profile, which is why it doesn't run automatically with a simple `docker compose up`.

To run the ingestion script once and see its output directly in your console, use the following command:

```bash
docker compose run --rm ingest
```

This command starts a container for the `ingest` service, runs `app/ingest.py` as defined in `docker-compose.yml`, and then automatically removes the container when it finishes. You will see the logs output directly in your terminal.

If you prefer to run it in the background using the profile, you can do:

```bash
docker compose --profile ingest up -d ingest
```

And then to view the logs for this background process:

```bash
docker compose logs -f ingest
```
