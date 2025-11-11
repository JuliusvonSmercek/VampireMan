module load python/3.12.9
source ~/venvs/VampireMan/bin/activate
cd /home/hofmanja/HeatPlumes/VampireMan
poetry env use python3.12
eval $(poetry env activate)
export PETSC_DIR=/home/hofmanja/petsc
export PETSC_ARCH=arch-linux-c-opt
export LD_LIBRARY_PATH=$PETSC_DIR/$PETSC_ARCH/lib:$LD_LIBRARY_PATH
export PATH=$PETSC_DIR/$PETSC_ARCH/bin:$PATH
alias mpirun='mpirun -x LD_LIBRARY_PATH'
case="case35_only_cooling"
dataset_out="case_35_only_cooling-5"
mkdir -p ./datasets_out/${dataset_out}
cp ./settings/${case}.yaml ./datasets_out/${dataset_out}/settings.yaml
python -m vampireman --non-interactive --settings-file ./settings/${case}.yaml && \
deactivate
