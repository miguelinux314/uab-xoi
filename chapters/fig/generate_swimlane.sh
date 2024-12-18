cd $(dirname $0)

rm -f *eps-converted-to.pdf

for f in *msc; do
   mscgen -i $f -T eps -o ${f%.msc}.eps
done

