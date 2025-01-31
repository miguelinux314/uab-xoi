all: code_output swimlane main.pdf

code_output:
	cd ./code && sudo python ./generate_output.py

swimlane:
	./chapters/fig/generate_swimlane.sh

main.pdf: *.tex chapters/*.tex
	pdflatex -shell-escape main
	# bibtex main
	pdflatex -shell-escape main
	pdflatex -shell-escape main

clean:
	rm -f *.blg *.bbl *.upa *.idx *.ind *.ilg *.aux *.upb *.bcf *.toc *.run.xml *.log *.ptc
