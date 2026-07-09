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

## Algorithm Overview

This application uses a combination of computer vision and vector database technologies to perform reverse image search.

### SIFT (Scale-Invariant Feature Transform)

The core algorithm used for image analysis is SIFT. SIFT detects distinct "keypoints" in an image—such as corners, edges, and other salient features. For each keypoint, it computes a 128-dimensional local image descriptor. These descriptors are designed to be highly robust; they remain relatively constant even if the image undergoes changes in scale (resizing), rotation, or minor variations in illumination.

### Vector Storage in Qdrant

Once the 128-dimensional descriptors are extracted from the dataset images, they are stored in a Qdrant vector database collection named `sift_features`.
*   Each vector in the database represents a single keypoint from an image.
*   Every vector is stored alongside a "payload" that contains the original source image's filename.
*   Qdrant is configured to use **Euclidean distance** to measure the similarity between vectors, making it highly efficient at finding nearest neighbors.

### The Matching Process

When a user uploads a query image for searching, the following steps occur:
1.  **Extraction**: SIFT features (descriptors) are extracted from the uploaded query image.
2.  **Search**: For every single descriptor found in the query image, a search is performed against the Qdrant database to retrieve the **5 nearest neighbors**.
3.  **Voting**: A voting mechanism tallies the results. Every time an image from the database appears in the nearest neighbors of a query descriptor, it receives a "vote" (a match).
4.  **Results**: The images that accumulate the most votes across all the query descriptors are determined to be the best matches and are returned to the user.
