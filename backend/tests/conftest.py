import os
import tempfile

# Cache SQLite isolé pour les tests (doit être défini avant l'import de app.*)
os.environ["CEPES_CACHE_DB"] = os.path.join(tempfile.mkdtemp(), "test-cache.sqlite")
