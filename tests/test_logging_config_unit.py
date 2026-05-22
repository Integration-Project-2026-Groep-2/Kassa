import logging
import time

import src.logging_config as logging_config


def test_rabbitmq_log_handler_queues_and_closes(monkeypatch):
    # Ensure worker returns quickly by disabling aio_pika path
    monkeypatch.setattr(logging_config, 'HAS_AIOPIKA', False)

    handler = logging_config.RabbitMQLogHandler(service_name='TEST')

    # Create a LogRecord and emit
    record = logging.LogRecord(name='t', level=logging.INFO, pathname=__file__, lineno=1, msg='hello', args=(), exc_info=None)
    handler.emit(record)

    # record should be enqueued
    assert not handler.log_queue.empty()

    # close should set stop_event and join thread
    handler.close()
    # allow thread to stop
    time.sleep(0.1)
    assert handler.stop_event.is_set()
