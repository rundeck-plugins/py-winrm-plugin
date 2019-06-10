FROM rundeck/rundeck:SNAPSHOT

USER root

RUN echo "deb http://archive.ubuntu.com/ubuntu xenial-updates main restricted universe multiverse /" | sudo tee -a /etc/apt/sources.list

RUN apt-get -y update && \
    apt-get -y install \
    software-properties-common  \
    apt-transport-https \
    iputils-ping \
    openssh-server \
    netcat-traditional \
    unzip \
    zip \
    vim \
    jq \
    sysstat

ARG PYTHON_VERSION

RUN echo ${PYTHON_VERSION}

RUN apt-get install -y libffi-dev

RUN apt-get install libssl-dev openssl gcc make -y && \
    cd /opt && \
    wget https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz && \
    tar xzvf Python-${PYTHON_VERSION}.tgz && \
    cd Python-${PYTHON_VERSION} && \
    ./configure --with-ensurepip=install && \
    make && \
    make install

ENV PATH="/opt/Python-${PYTHON_VERSION}:$PATH"

RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
RUN python get-pip.py

RUN apt-get install -y gcc python-dev libkrb5-dev krb5-user
## Install python winrm
RUN python -m pip install --upgrade pip && \
    python -m pip install setuptools --force --upgrade && \
    python -m pip install requests urllib3 pywinrm && \
    python -m pip install pywinrm[credssp] && \
    python -m pip install pywinrm[kerberos] && \
    python -m pip install pexpect

#set rundeck password
RUN echo 'rundeck:rundeck' | chpasswd

USER rundeck
ENV RDECK_BASE=/home/rundeck \
    USER=rundeck

ENV PATH="/opt/Python-${PYTHON_VERSION}:$PATH"

RUN mkdir data demo-projects

COPY --chown=root:root ./config/krb5.conf /etc/krb5.conf
COPY --chown=rundeck:root remco /etc/remco
COPY --chown=rundeck:root ./plugins ./libext

VOLUME ["/home/rundeck/server/data"]

EXPOSE 4440
ENTRYPOINT [ "docker-lib/entry.sh" ]
