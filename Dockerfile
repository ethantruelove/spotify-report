FROM python:3.11.10-alpine

RUN apk add build-base libpq libpq-dev

COPY ./requirements.txt ./requirements.txt

RUN pip install -U pip
RUN pip install -r ./requirements.txt

COPY ./app /opt/app/

COPY ./alembic /opt/alembic/
COPY ./alembic.ini /opt/

WORKDIR /opt/

EXPOSE 8080
EXPOSE 5432