Server use
----------

[Install celery 3.1+](http://docs.celeryproject.org/en/latest/getting-started/introduction.html#installation)

	# Assuming EL6 with EPEL installed
	yum -y install python-pip
	pip install celery

[Install rabbitmq](http://docs.celeryproject.org/en/latest/getting-started/brokers/rabbitmq.html)

	# Assuming EL6 with EPEL installed
	yum -y install rabbitmq-server
	service rabbitmq-server start
	chkconfig rabbitmq-server on

Install imapsync

	# Assuming EL6 with EPEL installed
	yum -y install imapsync

[Run the worker](http://docs.celeryproject.org/en/latest/getting-started/first-steps-with-celery.html#running-the-celery-worker-server)

	celery worker --loglevel=info


Client use
----------

The task is called with two host arguments. Each host must have the following keys

* host
* user
* password

The following optional keys are present

* encryption [ssl/tls]

Besides two hosts, an optional third argument can be given with the following optional keys

* feedback_email
* feedback_from_email

Example

	import tasks

	# Source host, encrypted with TLS
	source = {
		'host': 'mail-source.example.org',
		'user': 'source_user',
		'password': 'source_password',
		'encryption': 'tls',
	}

	# Destination host, unencrypted
	destination = {
	        'host': 'mail-destination.example.org',
	        'user': 'destination_user',
	        'password': 'destination_password',
	}

	# Options
	options = {
		'feedback_email': 'destination_user@example.org',
		'feedback_from_email': 'zarafa@example.org',
	}

	# Call the task
	task = tasks.imapsync.delay(source, destination, options)

	# Block till we get the result and print that
	print task.get()
