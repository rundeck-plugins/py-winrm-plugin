FROM ubuntu:16.04@sha256:1f1a2d56de1d604801a9671f301190704c25d604a416f59e03c04f5c6ffee0d6

## General package configuration
RUN apt-get -y update && \
    apt-get -y install \
        sudo \
        unzip \
        zip \
        curl \
        xmlstarlet \
        netcat-traditional \
        software-properties-common \
        debconf-utils \
        ncurses-bin \
        iputils-ping \
        net-tools \
        apt-transport-https \
        git  \
        jq

## Install Java
RUN \
  add-apt-repository -y ppa:openjdk-r/ppa  && \
  apt-get update && \
  apt-get install -y openjdk-8-jdk


# add GPG key
RUN curl "https://bintray.com/user/downloadSubjectPublicKey?username=bintray" > /tmp/bintray.gpg.key
RUN apt-key add - < /tmp/bintray.gpg.key

#Install Rundeck CLI tool
RUN echo "deb https://dl.bintray.com/rundeck/rundeck-deb /" | sudo tee -a /etc/apt/sources.list
RUN curl "https://bintray.com/user/downloadSubjectPublicKey?username=bintray" > /tmp/bintray.gpg.key
RUN apt-key add - < /tmp/bintray.gpg.key
RUN apt-get -y install apt-transport-https
RUN apt-get -y update
RUN apt-get -y install rundeck-cli


RUN mkdir -p scripts data
COPY scripts scripts

RUN chmod -R a+x scripts/*

CMD scripts/run.sh