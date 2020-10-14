FROM python:slim

WORKDIR /AI-Agent

RUN apt-get update && apt-get install -y git
COPY requirements.txt ./
RUN pip install -r requirements.txt

ADD prom_lib ./prom_lib
COPY mon_client.py  ./
COPY message_bus_client.py ./
COPY main.py  ./
RUN mkdir -p /etc/volume
CMD [ "python", "main.py" ]