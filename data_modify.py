import csv

input_file = 'data/data.csv'
output_file = 'data/data_new.csv'

# 建立日期對應表
date_map = {
    '2025-07-01': '2025-07-12',
    '2025-07-02': '2025-07-13',
    '2025-07-03': '2025-07-14',
    '2025-07-04': '2025-07-15',
    '2025-07-05': '2025-07-16',
    '2025-07-06': '2025-07-17',
    # 如果有更多天，請自行補齊
}

with open(input_file, newline='', encoding='utf-8') as csvfile, \
     open(output_file, 'w', newline='', encoding='utf-8') as outfile:
    reader = csv.reader(csvfile)
    writer = csv.writer(outfile)
    header = next(reader)
    writer.writerow(header)
    for row in reader:
        if row[3] in date_map:
            row[3] = date_map[row[3]]
        writer.writerow(row)

print('已完成日期批次修改，請使用 data_new.csv')