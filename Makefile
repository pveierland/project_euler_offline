python-lock:
	@uv pip compile \
		--generate-hashes ./requirements.in \
		--output-file ./requirements.txt \
		--quiet \
		&& ./python-requirements-prune \
		&& direnv reload

python-upgrade:
	@uv pip compile \
		--generate-hashes ./requirements.in \
		--output-file ./requirements.txt \
		--quiet \
		--upgrade \
		&& ./python-requirements-prune \
		&& direnv reload

