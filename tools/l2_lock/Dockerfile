# Dedicated test image; never derive from or override the Migration Guard image.
FROM python:3.12.16-slim-trixie@sha256:05a994d2344eb364cc186910f4fc8786a38215f39f00d0acc25bff33a08f4177
ARG BASE_REVISION
ARG SOURCE_SHA256
ARG TEST_SHA256
LABEL trendleader.l2.base-revision=$BASE_REVISION
LABEL trendleader.l2.source-sha256=$SOURCE_SHA256
LABEL trendleader.l2.test-sha256=$TEST_SHA256
ENV PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
WORKDIR /l2
RUN python -m pip install --no-cache-dir pytest==9.2.0 SQLAlchemy==2.0.57 PyMySQL==1.2.4 \
    && python -m pip check
COPY backend/tests/l2_lock/test_connection_lock.py /l2/test_connection_lock.py
COPY backend/tests/l2_lock/pytest.ini /l2/pytest.ini
RUN python -c "import hashlib, pathlib; assert hashlib.sha256(pathlib.Path('/l2/test_connection_lock.py').read_bytes()).hexdigest() == '${TEST_SHA256}'; assert len('${BASE_REVISION}') == 40"
RUN python -c "import hashlib, pathlib; d=hashlib.sha256(); [d.update(n.encode()+b'\0'+pathlib.Path('/l2',n).read_bytes()) for n in ('test_connection_lock.py','pytest.ini')]; assert d.hexdigest() == '${SOURCE_SHA256}'; assert '${BASE_REVISION}' == 'b6831cf5d855fa5b3b02adaf8a350f83ded86487'"
USER 1000:1000
ENTRYPOINT ["python", "-m", "pytest", "-c", "/l2/pytest.ini"]
CMD ["/l2/test_connection_lock.py", "--confcutdir=/l2", "-m", "integration", "-q", "--tb=no", "--show-capture=no", "-p", "no:cacheprovider", "--junitxml=/results/l2-report.xml"]
