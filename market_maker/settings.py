from dotenv import load_dotenv
import os

env_path = os.path.join(os.path.dirname(__file__),
                        '.env.%s' % os.getenv('ENVIRONMENT'))
load_dotenv(dotenv_path=env_path)
