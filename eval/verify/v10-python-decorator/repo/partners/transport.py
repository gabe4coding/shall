def with_timeout(seconds):
    """Give every call a timeout unless the caller passes one."""
    def decorate(fn):
        def call(*args, **kwargs):
            kwargs.setdefault("timeout", seconds)
            return fn(*args, **kwargs)
        return call
    return decorate
