# Access Log Exception Testing

How to verify that exception classification is working correctly in the access log.

## Exception Classification

The `exception_is_unexpected` column classifies each request:

| Scenario | `exception_is_unexpected` | `exception_traceback` |
|---|---|---|
| Successful request (2xx) | `NULL` | `NULL` |
| App-level exception (known user error) | `0` | `NULL` |
| Validation error | `0` | `NULL` |
| Unhandled exception (500) | `1` | Full traceback |

App-level exceptions are errors we explicitly raise because we know it's a user-side problem (invalid input, not found, permission denied, etc.). These don't need tracebacks since they're expected. Unhandled exceptions are bugs — they get full tracebacks for debugging.

## Shared Exception Class

Example of Exception Class. Services should raise this for known user errors:

```python
class ServiceException(HTTPException):
    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(status_code=status_code, detail=detail)
```

## Verification Steps

### 1. Add temporary test routes

```python
@app.get("/test_exc/ok")
async def test_ok():
    return {"status": "ok"}

@app.get("/test_exc/expected")
async def test_expected():
    raise ServiceException("This is a test error")

@app.get("/test_exc/unexpected")
async def test_unexpected():
    raise RuntimeError("Something went wrong unexpectedly")
```

### 2. Curl each endpoint

```bash
curl http://localhost/test_exc/ok
curl http://localhost/test_exc/expected
curl http://localhost/test_exc/unexpected
```

### 3. Query the access log database

```bash
sqlite3 -header -column run/access-log/access-log.db \
  "SELECT path, status_code, exception_class, exception_message,
          exception_is_unexpected, exception_traceback IS NOT NULL as has_traceback
   FROM access_log WHERE path LIKE '/test_exc%' ORDER BY id DESC LIMIT 3"
```

### 4. Expected output

```
path                  status_code  exception_class   exception_message                  exception_is_unexpected  has_traceback
--------------------  -----------  ----------------  ---------------------------------  -----------------------  -------------
/test_exc/unexpected  500          RuntimeError      Something went wrong unexpectedly  1                        1
/test_exc/expected    400          ServiceException  This is a test error               0                        0
/test_exc/ok          200                                                                                        0
```

### 5. Remove the test routes
