import logging
import signal
import time

from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.options import define, parse_command_line, options

from .app import ShoestringApplication


define('debug', default=False, type=bool, help='Run in debug mode')
define('port', default=8080, type=int, help='Server port')
define('allowed_hosts', multiple=True, help='Allowed hosts for cross domain connections')
define('backend', default='shoestring.backends.memory', help='Backend for storing connections.')
define('graceful', default=10, type=int, help='Max number of seconds to wait for a graceful shutdown.')


def shutdown(server, application, graceful=True, ioloop=None):
    ioloop = ioloop or IOLoop.current()
    if getattr(server, '_stopping', False):
        graceful = False
    else:
        server._stopping = True
        logging.info('Stopping server...')
        server.stop()
        logging.info('Stopping application...')
        application.shutdown(graceful=graceful)

    def finalize():
        ioloop.stop()
        logging.info('Stopped.')

    deadline = time.time() + options.graceful

    def poll():
        now = time.time()
        if now < deadline and (ioloop._callbacks or ioloop._timeouts):
            ioloop.add_timeout(now + 1, poll)
        else:
            finalize()

    if graceful:
        poll()
    else:
        finalize()


def main(ioloop=None):
    ioloop = ioloop or IOLoop.current()
    parse_command_line()
    application = ShoestringApplication(
        debug=options.debug, backend=options.backend, allowed_hosts=options.allowed_hosts)
    server = HTTPServer(application)
    server.listen(options.port)
    signal.signal(signal.SIGINT, lambda sig, frame: shutdown(server, application, graceful=True))
    signal.signal(signal.SIGTERM, lambda sig, frame: shutdown(server, application, graceful=True))
    signal.signal(signal.SIGALRM, lambda sig, frame: shutdown(server, application, graceful=True))
    signal.signal(signal.SIGQUIT, lambda sig, frame: shutdown(server, application, graceful=False))
    logging.info('Starting server on localhost:%d', options.port)
    if not ioloop._running:
        ioloop.start()


if __name__ == "__main__":  # pragma: no cover
    main()
