# Isbt: A Jupyter Kernel for sbt

See a notebook [example](https://github.com/ktr-skmt/Isbt/blob/master/examples/isbt_examples.ipynb)

To install,

1. git clone https://github.com/ktr-skmt/Isbt.git or download this [zipped repository](https://github.com/ktr-skmt/Isbt/archive/master.zip) and unzip it.
1. modify the Isbt Kernel spec [sbt/kernel.json](https://github.com/ktr-skmt/Isbt/blob/master/sbt/kernel.json) regarding a path to [SBTKernel.py](https://github.com/ktr-skmt/Isbt/blob/master/SBTKernel.py).
1. put [sbt/kernel.json](https://github.com/ktr-skmt/Isbt/blob/master/sbt/kernel.json) in your kernel specs' location (See [Kernel specs](http://jupyter-client.readthedocs.io/en/latest/kernels.html#kernelspecs)).
1. run "jupyter kernelspec list" to confirm whether sbt is registered.


To run,

1. run "sbt".
1. run "jupyter notebook".
1. make a new notebook with "sbt" Kernel.
1. execute "sbt-server help" to see help.
1. to connect to sbt server, do one of the following choices:
    * execute "sbt-server (host) (port)". Note that you can find the host and the port from your sbt log. If the log includes "[info] sbt server started at 127.0.0.1:12700", then the host is 127.0.0.1 and the port is 12700.
    * execute "sbt-server". It means "sbt-server localhost 12700" as default. Note that you can add a dedicated port in build.sbt like "serverPort := 12700".
1. You can use the notebook as if it were SBT Shell. Enjoy!

I have tested it in Python 3.6.1.
