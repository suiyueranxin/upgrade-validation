# Procedure to retrieve secrets used in the e2e tests:

There are a set of server configurations that need to be exported as environment parameters. The server configurations are located in file below.

Follow instructions below to retrieve file

## From Windows:

1. Copy the file from `\\build.pal.sap.corp\eiminfra1\eiminfra\bdhinfra\bdhautomation\export_windows`(if you are facing issues follow this troubleshooting) - expect some delay);
2. Rename the file as `export_windows.bat` (verify if a single apostophe was added for every single enviroment variable (E.g. export `dh_test_server_GCP_HANA='{"host": "35.240.32.21", "port": 30015, "user": "BDHE2ETESTS", "password": "Sapvora123"}'`);
3. Execute the bat file (to check if environment variables are set correctly run `echo $dh_test_server_WASB` from the terminal.

## From Linux

1. Create mount point: `mkdir -p /remote/eiminfra1/` and `mount -t nfs ns01vs012.pal.sap.corp:/vol/vol_eiminfra1 /remote/eiminfra1/`
2. Retrieve file `/remote/eiminfra1/eiminfra/bdhinfra/bdhautomation/export_linux_osx`
3. Source the file before running automation: `source export_linux_osx.sh`
4. To check if env variables are set correctly, run: `echo $dh_test_server_WASB`

## Then also add

export dh_test_server_ABAP_UK='{"protocol": "RFC", "ashost": "ldciuk5.wdf.sap.corp", "sysid": "UK5", "sysnr": "00", "client": "800", "user": "GUNDUZH", "password": "LoeEm55q", "sap_language": "EN", "gwhost": "ldciuk5.wdf.sap.corp"}'
