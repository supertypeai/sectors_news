import argparse
from scripts.server import post_source

def main():

  parser = argparse.ArgumentParser(description="Script for posting data from file")
  parser.add_argument("filenames", type=str, nargs='+', help="List of filenames")

  args = parser.parse_args()
  
  for filename in args.filenames:
    post_source(filename)

if __name__ == "__main__":
    main()

# python universal_pipeline.py filename