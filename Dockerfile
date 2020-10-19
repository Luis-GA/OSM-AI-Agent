FROM python:slim

WORKDIR /AI-Agent


COPY requirements.txt ./
RUN pip install -r requirements.txt

ADD prom_lib ./prom_lib

COPY main.py  ./
RUN mkdir -p /etc/volume
CMD [ "python", "main.py" ]