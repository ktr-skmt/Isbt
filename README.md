# Isbt: A Jupyter Kernel for sbt

See examples

To install,

1. git clone
1. modify a path to SBTKernel.py in the Isbt Kernel spec sbt/kernel.json
1. move sbt/kernel.json to your kernel
1. run "jupyter kernelspec list" to confirm whether sbt is registered


To run,

1. run "sbt"
1. run "jupyter notebook"
1. make a new notebook with "sbt" as Kernel
1. execute "sbt-server help" to see help
1. do one of the following choices:
    a. execute "sbt-server (host) (port)". Note that you can find host and port from your sbt log. If the log includes "[info] sbt server started at 127.0.0.1:12700", then the host is 127.0.0.1 and the port is 12700.
    a. execute "sbt-server" that means "sbt-server localhost 12700" as default. Note that you can add a dedicated port in build.sbt like "serverPort := 12700".
1. You can use the notebook as if it were SBT Shell. Enjoy!

I have tested it in Python 3.6.1.
