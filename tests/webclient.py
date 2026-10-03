"""A Flask test client that writes as the console's own page does: its Origin and the server's token on every request
(``jason.web.guard``). A test of the guard itself uses ``app.test_client()`` and sets the headers it means to test."""

ORIGIN = "http://localhost"


def client(app, *, token: bool = True, origin: str = ORIGIN):
    c = app.test_client()
    if origin:
        c.environ_base["HTTP_ORIGIN"] = origin
    if token:
        c.environ_base["HTTP_X_JASON_TOKEN"] = app.config["JASON_TOKEN"]
    return c
