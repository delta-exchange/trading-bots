from dotenv import load_dotenv
import os


dotenvs = os.getenv('DOTENVS').split(",")
for dotenv in dotenvs:
    env_path = os.path.join(os.path.dirname(__file__),
                            '.env.%s' % dotenv)
    load_dotenv(dotenv_path=env_path)
