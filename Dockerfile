FROM python:3.7-slim

RUN apt-get update && apt-get install -y curl git
RUN curl -L https://git.io/get_helm.sh | bash
RUN curl -LO https://storage.googleapis.com/kubernetes-release/release/`curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt`/bin/linux/amd64/kubectl
RUN chmod +x ./kubectl
RUN mv ./kubectl /usr/local/bin/kubectl
RUN helm init --client-only

RUN pip install pipenv
COPY /Pipfile  /app/Pipfile
COPY /Pipfile.lock  /app/Pipfile.lock
WORKDIR /app
RUN pipenv install --deploy
COPY . /app

CMD ["pipenv", "run", "python", "app.py"]
