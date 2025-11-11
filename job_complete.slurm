#!/bin/bash
#SBATCH --job-name=case35-4
#SBATCH --output=logs/case35-4.%j.out        # %j → job id
#SBATCH --error=logs/case35-4.%j.err
#SBATCH --time=2-00:00:00                    # hh:mm:ss

git checkout 
bash vampireman.sh