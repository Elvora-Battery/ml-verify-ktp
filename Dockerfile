FROM python:3.9-slim

ENV PYTHONUNBUFFERED True

# copy the local code
ENV APP_HOME /app
WORKDIR $APP_HOME 
COPY . ./

# install all package
RUN pip install -r requirements.txt

# Run webservices on container
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
