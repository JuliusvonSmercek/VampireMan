#!/bin/bash
#SBATCH --job-name=case35-5
#SBATCH --output=logs/case35-5.%j.out        # %j → job id
#SBATCH --error=logs/case35-5.%j.err
#SBATCH --time=2-00:00:00                    # hh:mm:ss

git checkout 6d2c185673856a7b94a6a373b80bdb174508baf2
bash vampireman.sh