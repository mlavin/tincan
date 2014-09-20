import logging
import signal
import sys
import time

from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.options import define, parse_command_line, options

from .app import ShoestringApplication


define('debug', default=False, type=bool, help='Run in debug mode')
define('port', default=8080, type=int, help='Server port')
define('allowed_hosts', multiple=True, help='Allowed hosts for cross domain connections')
define('backend', default='shoestring.backends.memory', help='Backend for storing connections.')
define('graceful', default=10, type=int, help='Max number of seconds to wait for a graceful shutdown.')


def shutdown(server, application, graceful=True):
    ioloop = IOLoop.instance()
    logging.info('Stopping server...')
    server.stop()
    logging.info('Stopping application...')
    application.shutdown()

    def finalize():
        ioloop.stop()
        logging.info('Stopped.')
        sys.exit(0)

    def poll(counts={'remaining': None, 'previous': None}):
        remaining = len(ioloop._handlers)
        counts['remaining'], counts['previous'] = remaining, counts['remaining']
        previous = counts['previous']
        # Wait until we only have only one IO handler remaining.  That
        # final handler will be our PeriodicCallback polling task.
        if remaining == 1:
            finalize()
        if previous is None or remaining != previous:
            logging.info("Waiting on IO %d remaining handlers", remaining)   

    if graceful:
        # Callback to check on remaining handlers.
        poller = PeriodicCallback(poll, 250, io_loop=ioloop)
        poller.start()

        ioloop.add_timeout(time.time() + options.graceful, finalize)
    else:
        finalize()


def main():
    parse_command_line()
    application = ShoestringApplication(debug=options.debug, backend=options.backend)
    server = HTTPServer(application)
    server.listen(options.port)
    signal.signal(signal.SIGINT, lambda sig, frame: shutdown(server, application, graceful=True))
    signal.signal(signal.SIGTERM, lambda sig, frame: shutdown(server, application, graceful=True))
    signal.signal(signal.SIGQUIT, lambda sig, frame: shutdown(server, application, graceful=False))
    logging.info('Starting server on localhost:%d', options.port)
    IOLoop.instance().start()


if __name__ == "__main__":
    main()
