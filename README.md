# cdte-iv-degradation-model

This repository houses a work-in-progress hybrid (physics-data driven) model for analysis of CdTe IV data from modules in operation. The goal is to construct modular code snippets capable of graphical presentation of raw data, correction based on Irradiance and device temperature, and 2-diode model parameter extraction.

# CdTe IV Degradation Model



This repository processes outdoor IV curve measurements from CdTe photovoltaic modules. The current pipeline ingests raw Fluke/Solmetric PVA CSV files, extracts IV curves and metadata, performs basic quality control, applies first-pass CdTe environmental corrections, and generates diagnostic plots.



The long-term goal is to support CdTe reliability analysis and eventually diode-model-based degradation tracking.





==================================================

1\. EXPECTED REPOSITORY STRUCTURE

==================================================



cdte-iv-degradation-model/

│

├── data/

│   ├── raw\_iv\_traces/

│   └── processed\_iv\_traces/

│

├── outputs/

│   ├── figures/

│   └── fitted\_parameters/

│

├── src/

│   ├── io/

│   │   └── parse\_iv\_files.py

│   │

│   ├── analysis/

│   │   └── qc\_and\_correct\_metadata.py

│   │

│   └── plotting/

│       ├── plot\_iv\_curves.py

│       └── plot\_corrected\_trends.py

│

├── config/

├── notebooks/

├── .gitignore

└── README.md





==================================================

2\. RAW DATA FOLDER FORMAT

==================================================



Place raw IV data in:



data/raw\_iv\_traces/



Structure:



data/raw\_iv\_traces/

└── bay\_2\_bad/

&#x20;   ├── 114/

&#x20;   │   ├── CSV files

&#x20;   ├── 126/

&#x20;   │   ├── CSV files



Recommended pattern:



data/raw\_iv\_traces/<bay\_name>/<module\_id>/\*.csv



Examples:



data/raw\_iv\_traces/bay\_2\_bad/114/file.csv

data/raw\_iv\_traces/bay\_5/201/file.csv



Scripts automatically scan all folders recursively.





==================================================

3\. WORKFLOW

==================================================



Run from repo root:



cd C:\\Users\\maxli\\Documents\\cdte-iv-degradation-model



Then execute:



python src\\io\\parse\_iv\_files.py

python src\\analysis\\qc\_and\_correct\_metadata.py

python src\\plotting\\plot\_iv\_curves.py

python src\\plotting\\plot\_corrected\_trends.py





==================================================

4\. SCRIPT DESCRIPTIONS

==================================================



\----------------------------------

4.1 parse\_iv\_files.py

\----------------------------------



Purpose:

\- Parses raw CSV files

\- Extracts IV curves and metadata



Input:

data/raw\_iv\_traces/



Outputs:

data/processed\_iv\_traces/

outputs/fitted\_parameters/iv\_metadata\_summary.csv



Extracted values:

\- voltage, current, power

\- measured Pmax, Vmpp, Impp, Voc, Isc

\- predicted values

\- irradiance

\- temperature

\- module ID and bay



Run:

python src\\io\\parse\_iv\_files.py





\----------------------------------

4.2 qc\_and\_correct\_metadata.py

\----------------------------------



Purpose:

\- Adds QC flags

\- Applies simple CdTe corrections



Input:

outputs/fitted\_parameters/iv\_metadata\_summary.csv



Output:

outputs/fitted\_parameters/iv\_metadata\_qc\_corrected.csv



QC checks:

\- missing datetime

\- missing irradiance

\- missing temperature

\- low irradiance

\- missing electrical data

\- module ID mismatch

\- duplicate entries



New columns:

\- isc\_norm\_a

\- voc\_temp\_corr\_v

\- pmax\_irradiance\_norm\_w

\- pmax\_simple\_corr\_w



Run:

python src\\analysis\\qc\_and\_correct\_metadata.py





==================================================

5\. ENVIRONMENTAL CORRECTIONS

==================================================



Reference conditions:

G\_ref = 1000 W/m^2

T\_ref = 25 C



Isc normalization:



Isc\_norm = Isc\_meas \* (G\_ref / G\_meas) / (1 + alpha\_Isc \* (T\_meas - T\_ref))



Voc correction:



Voc\_corr = Voc\_meas + beta\_Voc \* (T\_meas - T\_ref)



Pmax irradiance normalization:



Pmax\_irradiance\_norm = Pmax\_meas \* (G\_ref / G\_meas)



Simple corrected Pmax:



Pmax\_simple\_corr = Pmax\_meas \* (G\_ref / G\_meas) \* (Voc\_corr / Voc\_meas)



NOTE:

This is a simplified correction, not IEC translation.





==================================================

6\. CdTe METASTABILITY LIMITATION

==================================================



CdTe modules exhibit metastability (wakeup behavior).



Performance depends on:

\- prior illumination

\- temperature history

\- bias conditions

\- time since sunrise



This dataset does NOT include that history.



Therefore:

Metastability CANNOT be removed with current data.



Treat it as intrinsic uncertainty.



Do NOT interpret corrected Pmax as pure degradation yet.





==================================================

7\. PLOTTING SCRIPTS

==================================================



\----------------------------------

plot\_iv\_curves.py

\----------------------------------



Plots:

\- IV curves

\- raw parameter trends



Input:

iv\_metadata\_summary.csv



Output:

outputs/figures/



Run:

python src\\plotting\\plot\_iv\_curves.py





\----------------------------------

plot\_corrected\_trends.py

\----------------------------------



Plots:

\- raw vs corrected Pmax

\- raw vs corrected Voc

\- normalized Isc

\- corrected trends over time



Input:

iv\_metadata\_qc\_corrected.csv



Output:

outputs/figures/



Run:

python src\\plotting\\plot\_corrected\_trends.py





==================================================

8\. ADDING MORE DATA

==================================================



Add new folders:



data/raw\_iv\_traces/bay\_5/



Then rerun:



python src\\io\\parse\_iv\_files.py

python src\\analysis\\qc\_and\_correct\_metadata.py

python src\\plotting\\plot\_iv\_curves.py

python src\\plotting\\plot\_corrected\_trends.py





==================================================

9\. GIT NOTES

==================================================



Commit:

\- src/

\- README.md



Ignore:

data/

outputs/



.gitignore should include:



data/raw\_iv\_traces/

data/processed\_iv\_traces/

outputs/





==================================================

10\. CURRENT STATUS

==================================================



DONE:

\- parsing

\- metadata extraction

\- QC checks

\- basic corrections

\- plotting



NOT DONE:

\- diode model fitting

\- IEC correction

\- degradation modeling

\- metastability modeling





==================================================

11\. NEXT STEPS

==================================================



1\. Collect more time points

2\. Validate corrections vs irradiance and temperature

3\. Normalize per module

4\. Add degradation rate analysis

5\. Add diode model fitting

6\. Treat metastability as uncertainty



