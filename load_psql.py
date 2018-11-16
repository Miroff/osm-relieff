import os


args_input = 'contours-json'

files = map(lambda f: os.path.join(args_input, f), os.listdir(args_input))

for file in files:
    os.system("""ogr2ogr -f "PostgreSQL" PG:"host=localhost dbname=relief user=relief password=relieff" "%s" -nln relief -append""" % file)
