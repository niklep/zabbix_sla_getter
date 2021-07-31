#! /bin/sh

python3 /var/lib/zabbix/zabbix_sla_getter/zabbix_sla_getter.py
test -f /var/lib/zabbix/zabbix_sla_getter/result.txt
if [ $? -eq 1 ]
then
    # если result.txt не был создан, отправить в заббикс инфу о пробелеме (и будет алерт)
    /usr/bin/zabbix_sender -c /etc/zabbix/zabbix_agentd.conf -k zabbix_sla_getter -o 1
    exit 1
fi

cat /var/lib/zabbix/zabbix_sla_getter/result.txt | mailx -r $1 -s "Zabbix SLA information" $*
/usr/bin/zabbix_sender -c /etc/zabbix/zabbix_agentd.conf -k zabbix_sla_getter -o $?

month=$(date '+%Y-%m')
# складываем файл с результатом в директорию
mv /var/lib/zabbix/zabbix_sla_getter/result.txt /var/lib/zabbix/zabbix_sla_getter_results/result_${month}.txt

