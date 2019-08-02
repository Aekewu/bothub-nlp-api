# Bothub NLP - Natural Language Processing services

![version 2.2.0](https://img.shields.io/badge/version-2.2.0-blue.svg) [![python 3.6](https://img.shields.io/badge/python-3.6-green.svg)](https://docs.python.org/3.6/whatsnew/changelog.html) [![license AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-red.svg)](https://github.com/udomobi/bothub-nlp/blob/master/LICENSE)

Check the [main Bothub project repository](https://github.com/Ilhasoft/bothub).


## Services

### bothub-nlp-api

### bothub-nlp-nlu-worker

### bothub-nlp-nlu-worker-on-demand

## Packages

### bothub-nlp (python 3.6)

### bothub-nlp-celery (python 3.6)

### bothub-nlp-nlu (python 3.6)


# Requirements

* Python (3.6)
* Docker
* Docker-Compose

## Development

Use ```make``` commands to ```lint```, ```test```, ```mode_development```, ```dev_update```.

| Command | Description |
|--|--|
| make lint | Show lint warnings and errors
| make test | Run unit tests
| make mode_development | Create .env with variable environment and start build docker
| make dev_update | Updates containers docker that have changed


## Environment Variables

You can set environment variables in your OS, write on ```.env``` file or pass via Docker config.

| Variable | Type | Default | Description |
|--|--|--|--|
| SECRET_KEY | ```string```|  ```None``` | A secret key for a particular Django installation. This is used to provide cryptographic signing, and should be set to a unique, unpredictable value.
| DEBUG | ```boolean``` | ```False``` | A boolean that turns on/off debug mode.
| BOTHUB_NLP_DEBUG | ```boolean``` | ```False``` | A boolean that turns on/off debug mode.
| BOTHUB_NLP_DEVELOPMENT_MODE | ```boolean``` | ```False``` | A boolean that turns on/off development mode.
| DEFAULT_DATABASE | ```string``` | ```sqlite:///db.sqlite3``` | Read [dj-database-url](https://github.com/kennethreitz/dj-database-url) to configure the database connection.
| SUPPORTED_LANGUAGES | ```string```| ```en\|pt``` | Set supported languages. Separe languages using ```\|```. You can set location follow the format: ```[LANGUAGE_CODE]:[LANGUAGE_LOCATION]```.
| BOTHUB_NLP_SENTRY_CLIENT | ```string``` | ```None``` | 
| BOTHUB_NLP_CELERY_BROKER_URL | ```string``` | ```None``` | 
| BOTHUB_NLP_CELERY_BACKEND_URL | ```string``` | ```None``` | 
| BOTHUB_NLP_NLU_AGROUP_LANGUAGE_QUEUE | ```boolean``` | ```False``` | 
| BOTHUB_NLP_API_LOGGER_FORMAT | ```string``` | ```None``` | 
| BOTHUB_NLP_API_LOGGER_LEVEL | ```integer``` | ```10``` | 
| BOTHUB_NLP_AWS_S3_BUCKET_NAME | ```string``` | ```None``` | 
| BOTHUB_NLP_AWS_ACCESS_KEY_ID | ```string``` | ```None``` | 
| BOTHUB_NLP_AWS_SECRET_ACCESS_KEY | ```string``` | ```None``` | 
| BOTHUB_NLP_DOCKER_CLIENT_BASE_URL | ```string``` | ```None``` | 


## Docker Arguments

You need to set --build-arg when you are building docker-compose

| Argument | Type | Default | Description |
|--|--|--|--|
| DOWNLOAD_SPACY_MODELS | ```string```|  ```en:en_core_web_md``` | Set supported languages. Separe languages using ```\|```. You can set location follow the format: ```[LANGUAGE_CODE]:[LANGUAGE_LOCATION]```.
