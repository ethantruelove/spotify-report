FROM python:3.11.10-alpine

WORKDIR /opt/code

COPY ./requirements.txt ./requirements.txt

RUN pip install -U pip
RUN pip install -r requirements.txt

ENV POSTGRES_USER=admin
ENV POSTGRES_PASSWORD=admin
ENV POSTGRES_DB=spotify

COPY ./src ./

EXPOSE 8080