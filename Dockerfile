FROM public.ecr.aws/lambda/python:3.9

COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY src/* ${LAMBDA_TASK_ROOT}

CMD ["app.lambda_handler"]