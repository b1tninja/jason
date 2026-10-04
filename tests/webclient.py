"""A Flask test client that writes as the console's own page does: its Origin and the server's token on every request
(``jason.web.guard``). A test of the guard itself uses ``app.test_client()`` and sets the headers it means to test.

``roster_sign_in`` is Google sign-in set up with a made-up roster and nothing reaching Google or Keeper; ``sign_in``
puts a roster person's account in a client's session, as the callback does after Google answers."""

ORIGIN = "http://localhost"

# A made-up roster: each office once, a person holding two, a portfolio manager, and an admin with no office.
ROSTER = (
    ("A Manager", "manager", "a.manager@example.org", False),
    ("Pat Example", "treasurer", "pat@example.org", False),
    ("Dana Director", "director", "dana@example.org", False),
    ("Sam Secretary", "secretary", "sam@example.org", False),
    ("Lee President", "president", "lee@example.org", False),
    ("Vic Vice", "vice president", "vic@example.org", False),
    ("Tess Two", "secretary, treasurer", "tess@example.org", False),
    ("Ada Admin", "admin", "ada@example.org", True),
)


def client(app, *, token: bool = True, origin: str = ORIGIN):
    c = app.test_client()
    if origin:
        c.environ_base["HTTP_ORIGIN"] = origin
    if token:
        c.environ_base["HTTP_X_JASON_TOKEN"] = app.config["JASON_TOKEN"]
    return c


def roster_people(rows=ROSTER):
    from jason.web.signin import Person

    return tuple(Person(name, role, email, admin) for name, role, email, admin in rows)


def roster_sign_in(rows=ROSTER, *, configured: bool = True, dev: bool = False, required: bool = False):
    """Sign-in set up (one provider whose client is made up) over ``rows``; ``configured`` False is none set up."""
    from jason.web.signin import Client, Provider, SignIn

    provider = Provider("google", "", "community", ("example.org",), lambda: Client("cid", "secret"))
    people = roster_people(rows)
    return SignIn(providers=lambda: (provider,) if configured else (), roster=lambda: people,
                  exchange=lambda *a: {}, dev=dev, required=required)


def sign_in(c, name: str = "A Manager", *, rows=ROSTER, sub: str = ""):
    """``c``'s session signed in as ``name`` from ``rows``, with Google's ``sub`` (default: one from the name)."""
    person = next(p for p in roster_people(rows) if p.name == name)
    with c.session_transaction() as s:
        s["account"] = {"name": person.name, "role": person.role, "email": person.email,
                        "sub": sub or "sub-" + person.name.lower().replace(" ", "-"), "at": "2026-10-03T12:00:00+00:00",
                        "admin": person.admin, "provider": "google"}
    return c
