localcfg := ./localcfg.sh
wificfg := ./wifi.json

outdir := ./flash
codefiles := ./src/main.py ./src/perthensis.py ./src/sds011.py

define rshell =
. $(localcfg) && rshell
endef

outdir: $(localcfg) $(wificfg)
	rm -rf "$(outdir)"
	mkdir -p "$(outdir)"
	cp -a $(codefiles) $(wificfg) $(outdir)

flash: outdir
	$(rshell) 'rsync --mirror $(outdir) /pyboard'

repl: $(localcfg)
	$(rshell) repl

.PHONY: flash repl
