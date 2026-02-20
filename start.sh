  #!/bin/bash                                                                                                                                                                                                                                                           cd /home/ubuntu/SKN21-FINAL-3TEAM                                                                                                                                                                                                                                   
  cd /home/ubuntu/SKN21-FINAL-3TEAM
  export PYTHONPATH=/home/ubuntu/SKN21-FINAL-3TEAM:/home/ubuntu/SKN21-FINAL-3TEAM/backend   
  exec /home/ubuntu/SKN21-FINAL-3TEAM/.venv/bin/uvicorn backend.app.main:app \
    --host 0.0.0.0 --port 8000