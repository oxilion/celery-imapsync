import pprint
import smtplib
import sys
from celery.task import task
from celery.utils.log import get_task_logger
from email.mime.text import MIMEText
from subprocess import PIPE, Popen
from threading import Thread

try:
    from Queue import Queue, Empty
except ImportError:
    from queue import Queue, Empty  # python 3.x

logger = get_task_logger(__name__)

ON_POSIX = 'posix' in sys.builtin_module_names


def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    queue.task_done()
    out.close()


def get_imapsync_host_args(i, host):
    if not all(host.get(x) for x in ('host', 'user', 'password')):
        raise ValueError('Missing value for host')

    args = [
        '--host%d' % i, host['host'],
        '--user%d' % i, host['user'],
        '--password%d' % i, host['password'],
    ]

    if host.get('encryption') == 'tls':
        args.append('--tls%d' % i)
    elif host.get('encryption') == 'ssl':
        args.append('--ssl%d' % i)

    return args


@task(bind=True)
def imapsync(self, host1, host2, options={}):
    """
    Run imap synchronization.

    This is a light wrapper around imapsync.
    https://fedorahosted.org/imapsync/.
    """

    # Start imapsync
    command = (['imapsync', '--nolog --noreleasecheck'] +
               get_imapsync_host_args(1, host1) +
               get_imapsync_host_args(2, host2))

    logger.info('Starting sync from %s@%s to %s@%s with %r', host1['user'],
            host1['host'], host2['user'], host2['host'], options)
    process = Popen(command, stdout=PIPE, bufsize=1, close_fds=ON_POSIX)

    # Open a queue to put the output of imapsync
    q = Queue()
    q.put('++++ Started\n')

    # Start the thread that reads the output
    t = Thread(target=enqueue_output, args=(process.stdout, q))
    t.daemon = True
    t.start()

    # read output
    result = {}
    state = None
    while True:
        try:
            line = q.get(timeout=5)
        except Empty:
            if not t.is_alive():
                break
        else:  # got line
            line = line.rstrip()
            logger.debug(line)

            if line.startswith('++++ '):
                if line.startswith('++++ Calculating sizes on Host'):
                    state = 'CALCULATING'
                elif line == '++++ Listing folders':
                    state = 'LISTING'
                elif line == '++++ Looping on each folder':
                    state = 'SYNCING'
                elif line == '++++ Statistics':
                    state = 'STATISTICS'
                else:
                    try:
                        state = line.split()[1].upper()
                    except IndexError:
                        pass

                logger.info('Changed state to %s', state)
                self.update_state(state=state)
            elif state == 'STATISTICS':
                if ':' in line:
                    key, value = line.split(':', 1)
                    result[key.strip()] = value.strip()

    # Set the output status
    process.wait()

    # Store the resultcode
    result['returncode'] = process.returncode
    logger.info('Syncer completed with %s',
                'success' if process.returncode == 0 else 'failure')

    if options.get('feedback_to_email') and options.get('feedback_from_email'):
        self.update_state(state='SENDING_FEEDBACK_EMAIL')

        to_email = options['feedback_to_email']
        from_email = options['feedback_from_email']
        logger.info('Sending feedback email to %s from %s', to_email,
                    from_email)

        message = MIMEText(pprint.pformat(result))
        message['Subject'] = ('IMAP Sync completed with %s' %
                ('success' if process.returncode == 0 else 'failure'))
        message['From'] = from_email
        message['To'] = to_email

        s = smtplib.SMTP('localhost')
        s.sendmail(from_email, [to_email], message.as_string())
        s.quit()

    return result
