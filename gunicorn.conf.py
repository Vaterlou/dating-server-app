# gunicorn.conf.py
workers = 3
bind = 'localhost:8000'
timeout = 120
loglevel = 'debug'

# certfile = '/Users/denisgoncarov/PycharmProjects/dating-server-app/certificates/cert.pem'
# keyfile = '/Users/denisgoncarov/PycharmProjects/dating-server-app/certificates/key.pem'
#
# ssl_certfile = certfile
# ssl_keyfile = keyfile