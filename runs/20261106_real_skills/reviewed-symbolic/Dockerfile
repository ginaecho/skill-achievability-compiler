FROM python@sha256:4840d514c583a4d3d8cad3940e68dee6f0f6f3635c12fcd0a3d74c21a5b93a54
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_INDEX=1 PIP_CONSTRAINT=/opt/skillc/constraints.txt
COPY constraints.txt /opt/skillc/constraints.txt
COPY *.whl wheel_sha256.txt /opt/skillc/wheels/
RUN cd /opt/skillc/wheels \
    && sha256sum --check wheel_sha256.txt \
    && python -B -m pip install --no-deps --no-compile mpmath-1.3.0-py3-none-any.whl sympy-1.14.0-py3-none-any.whl \
    && python -B -m pip check \
    && python -I -B -c "import sympy,mpmath; assert sympy.__version__ == '1.14.0' and mpmath.__version__ == '1.3.0'"
