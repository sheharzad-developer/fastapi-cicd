# Task Management API

A small REST API for managing tasks, built with FastAPI, containerized with Docker,
tested and published by a GitHub Actions pipeline, and deployed on AWS EC2.

**Deployment:** deployed on AWS EC2 during development, then terminated to avoid charges.
See the Deploy to AWS section to recreate it.

## Tech stack

- Python 3.12, FastAPI, Pydantic
- pytest for automated tests
- Docker, with images published to Docker Hub
- GitHub Actions for CI/CD
- AWS EC2 (Arm `t4g.micro`) for hosting

## API endpoints

| Method | Path | Description | Success |
|---|---|---|---|
| GET | `/health` | Health check | 200 |
| POST | `/tasks` | Create a task | 201 |
| GET | `/tasks` | List all tasks | 200 |
| GET | `/tasks/{task_id}` | Get one task | 200 |
| PUT | `/tasks/{task_id}` | Update a task (partial) | 200 |
| DELETE | `/tasks/{task_id}` | Delete a task | 200 |

### Validation and errors

| Situation | Status |
|---|---|
| Empty or missing title, title over 200 characters, or invalid status | 422 |
| Non-integer task id (`/tasks/abc`) | 422 |
| Task does not exist | 404 |
| PUT with no fields | 400 |

A task has `title` (required), `description` (optional) and `status`
(`pending`, `in_progress` or `completed`; default `pending`).

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for the interactive API documentation.

`requirements.txt` holds the runtime dependencies used by the Docker image.
`requirements-dev.txt` adds pytest and httpx for testing.

## Run the tests

```bash
pytest -v
```

The `client` fixture in `tests/conftest.py` clears the in-memory task list before every
test, so tests do not affect each other. `pytest.ini` puts the project root on the import
path so `from app import main` works.

## Run with Docker

```bash
docker build -t task-api:1.0 .
docker run -d --name task-api -p 8000:8000 task-api:1.0
curl http://localhost:8000/health
```

Stop and remove it with `docker rm -f task-api`.

The image runs as a non-root user and defines a `HEALTHCHECK` that calls `/health`.
`docker ps` shows `(healthy)` once it passes. The server binds to `0.0.0.0`; the default
`127.0.0.1` would be unreachable from outside the container.

## Architecture

```
git push -> GitHub Actions: test -> build -> smoke test -> push image -> Docker Hub
                                                                            |
                                                docker pull (manual step)   v
Browser / curl --HTTP:80--> EC2 security group --> Docker container (uvicorn :8000)
```

- One FastAPI container. Tasks are held in memory.
- GitHub Actions builds the image on an Arm runner because the server is an Arm (`t4g`)
  instance. An image only runs on the CPU type it was built for.
- The EC2 security group is the firewall: SSH (22) is limited to the administrator's IP
  and HTTP (80) is open to the internet.

## CI/CD pipeline

`.github/workflows/ci.yml` runs on every push and pull request to `main`.

1. **test**: installs `requirements-dev.txt` and runs `pytest -v`.
2. **build** (runs only if `test` passes, via `needs: test`):
   - builds the Docker image,
   - starts the container and polls `/health` as a smoke test,
   - on pushes only (never on pull requests), logs in to Docker Hub and pushes two tags:
     `latest` and the commit SHA. The SHA tag identifies exactly which commit an image
     came from and allows rollback.

Required repository secrets (Settings, Secrets and variables, Actions):

| Secret | Value |
|---|---|
| `DOCKERHUB_USERNAME` | Docker Hub username |
| `DOCKERHUB_TOKEN` | Docker Hub access token with Read & Write permission |

Images are published to `docker.io/<username>/fastapi-cicd`.

## Deploy to AWS (EC2)

### 1. Launch the instance (EC2 console)

| Setting | Value |
|---|---|
| AMI | Amazon Linux 2023, 64-bit (Arm) |
| Instance type | `t4g.micro` |
| Key pair | RSA `.pem` (downloadable only once) |
| Security group | SSH (22) from My IP; HTTP (80) from `0.0.0.0/0` |

Use the same AWS region for every step; the console only shows resources in the selected
region.

### 2. Connect and install Docker

```bash
chmod 400 ~/Downloads/fastapi-key.pem
ssh -i ~/Downloads/fastapi-key.pem ec2-user@<PUBLIC_IP>

sudo dnf install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
exit        # log in again so the group change applies
```

### 3. Run the container

```bash
docker run -d --name fastapi-cicd --restart unless-stopped -p 80:8000 \
  <DOCKERHUB_USERNAME>/fastapi-cicd:latest
```

`-p 80:8000` maps the public port 80 to the app's port 8000.
`--restart unless-stopped` restarts the container after a crash or reboot.

### 4. Verify

```bash
docker ps
curl http://localhost/health        # on the server
```

Then open `http://<PUBLIC_IP>/health` and `http://<PUBLIC_IP>/docs` from a browser
(use `http://`, not `https://`).

### 5. Deploy a new version

After the pipeline has pushed a new image:

```bash
docker pull <DOCKERHUB_USERNAME>/fastapi-cicd:latest
docker rm -f fastapi-cicd
docker run -d --name fastapi-cicd --restart unless-stopped -p 80:8000 \
  <DOCKERHUB_USERNAME>/fastapi-cicd:latest
```

### Cost and cleanup

A `t4g.micro` costs roughly one cent per hour while running. When finished, terminate the
instance (EC2, Instance state, Terminate instance). Stopping it does not delete the disk,
and the public IP changes if it is stopped and started.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `fixture 'client' not found` (all tests ERROR) | Test config file misnamed, for example `confest.py` | Name it exactly `conftest.py` |
| `ModuleNotFoundError: No module named 'app'` in pytest | Project root not on the import path | Add `pytest.ini` containing `pythonpath = .` |
| `NameError: name 'X' is not defined` | Typo or missing import | Read the last line of the traceback; add the import |
| `docker build` says it requires 1 argument | Missing `.` (build context) | `docker build -t name .` |
| `Conflict. The container name ... is already in use` | A container with that name exists | `docker rm -f <name>` |
| `port is already allocated` | Another container uses the host port | `docker ps`, then stop or remove it |
| Actions: `Username and password required` | Docker Hub secrets missing or misnamed | Add `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` as repository secrets |
| `exec format error` in `docker logs` | Image CPU type differs from the server (amd64 vs Arm) | Build on an Arm runner (`ubuntu-24.04-arm`) for a `t4g` server |
| SSH `Operation timed out` | Security group SSH rule does not match your current IP | Set the SSH source to My IP again |
| `Could not resolve hostname` | The `<PUBLIC_IP>` placeholder was typed literally | Use the real Public IPv4 address |
| Port 80 times out from the internet | No HTTP rule on the instance's security group | Add an HTTP inbound rule (`0.0.0.0/0`) to the group shown on the instance's Security tab |
| Port 80 says `Connection refused` | Firewall open but nothing listening | `docker ps -a`; run with `-p 80:8000` |
| EC2 instance list is empty | Wrong region selected in the console | Switch to the region the instance was launched in |

A **timeout** means the firewall or network dropped the packets; **refused** means they
arrived and nothing was listening. Prompts help too: `[ec2-user@ip-...]` is the server, and
your own username and machine name is your laptop.

## Limitations and next steps

- **In-memory storage:** tasks are lost when the container restarts. A database (SQLite on
  a volume, or RDS) would make them persistent.
- **HTTP only:** the service is served on port 80. For production, add TLS with an
  Application Load Balancer and an ACM certificate on a custom domain, and open port 443.
- **Manual deploy step:** the pipeline publishes the image, but pulling it onto the server
  is manual. It could be automated with AWS Systems Manager or by moving to ECS.
- **Single instance:** no load balancing or automatic recovery.
