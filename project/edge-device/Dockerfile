FROM python:3

ADD edge-device.py /
ADD requirements.txt /

RUN pip3 install -r requirements.txt

CMD [ "python", "./edge-device.py" ]
