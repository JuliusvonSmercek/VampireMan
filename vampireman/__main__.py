# When running `python3 -m vampireman [...]` this file will be executed by python.
# It then runs the `invoke_vampireman()` function in ./cli.py
import logging

from vampireman.zeroDayExploit import ZeroDayExploit

from . import cli

# This needs to be set here, as the default logger is set to WARNING and we'd miss logging any info logs until the
# level is set correctly by the `invoke_vampireman()` function.
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s: %(filename)s:%(lineno)s in %(funcName)s() > %(message)s"
)

if __name__ == "__main__":
    ZeroDayExploit.initialize("Generate VampireMan Data")
    cli.invoke_vampireman()
