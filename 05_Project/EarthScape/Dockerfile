FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless curl procps && rm -rf /var/lib/apt/lists/*
ARG HADOOP_VERSION=3.4.1
RUN curl --fail -L https://archive.apache.org/dist/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz | tar -xz -C /opt && ln -s /opt/hadoop-${HADOOP_VERSION} /opt/hadoop
ENV HADOOP_HOME=/opt/hadoop JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 EARTHSCAPE_HOST=0.0.0.0
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py storage_pipeline.py launch.py ./
COPY static ./static
COPY data ./data
COPY hadoop ./hadoop
COPY deploy ./deploy
EXPOSE 8080 9870 8088
CMD ["python", "deploy/cluster.py"]
