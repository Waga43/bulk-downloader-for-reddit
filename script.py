#!/usr/bin/env python

"""
This program downloads imgur, gfycat and direct image and video links of 
saved posts from a reddit account. It is written in Python 3.
"""

import argparse
import logging
import os
import sys
import time
import webbrowser
from io import StringIO
from pathlib import Path, PurePath

from src.downloaders.Direct import Direct
from src.downloaders.Erome import Erome
from src.downloaders.Gfycat import Gfycat
from src.downloaders.Imgur import Imgur
from src.downloaders.redgifs import Redgifs
from src.downloaders.selfPost import SelfPost
from src.downloaders.gifDeliveryNetwork import GifDeliveryNetwork
from src.errors import ImgurLimitError, NoSuitablePost, FileAlreadyExistsError, ImgurLoginError, NotADownloadableLinkError, NoSuitablePost, full_exc_info
from src.parser import LinkDesigner
from src.searcher import getPosts
from src.utils import (GLOBAL, createLogFile, nameCorrector,
                       printToFile)
from src.jsonHelper import JsonFile
from src.config import Config
from src.arguments import Arguments
from src.programMode import ProgramMode

__author__ = "Ali Parlakci"
__license__ = "GPL"
__version__ = "1.7.0"
__maintainer__ = "Ali Parlakci"
__email__ = "parlakciali@gmail.com"

def postFromLog(fileName):
    """Analyze a log file and return a list of dictionaries containing
    submissions
    """
    if Path.is_file(Path(fileName)):
        content = JsonFile(fileName).read()
    else:
        print("File not found")
        sys.exit()

    try:
        del content["HEADER"]
    except KeyError:
        pass

    posts = []

    for post in content:
        if not content[post][-1]['TYPE'] == None:
            posts.append(content[post][-1])

    return posts

def isPostExists(POST,directory):
    """Figure out a file's name and checks if the file already exists"""

    filename = GLOBAL.config['filename'].format(**POST)

    possibleExtensions = [".jpg",".png",".mp4",".gif",".webm",".md"]

    for extension in possibleExtensions:

        path = directory / Path(filename+extension)

        if path.exists():
            return True

    else:
        return False

def downloadPost(SUBMISSION,directory):

    global lastRequestTime
    lastRequestTime = 0

    downloaders = {
        "imgur":Imgur,"gfycat":Gfycat,"erome":Erome,"direct":Direct,"self":SelfPost,
        "redgifs":Redgifs, "gifdeliverynetwork": GifDeliveryNetwork
    }

    print()
    if SUBMISSION['TYPE'] in downloaders:

        # WORKAROUND FOR IMGUR API LIMIT
        if SUBMISSION['TYPE'] == "imgur":
            
            while int(time.time() - lastRequestTime) <= 2:
                pass

            credit = Imgur.get_credits()

            IMGUR_RESET_TIME = credit['UserReset']-time.time()
            USER_RESET = ("after " \
                            + str(int(IMGUR_RESET_TIME/60)) \
                            + " Minutes " \
                            + str(int(IMGUR_RESET_TIME%60)) \
                            + " Seconds") 
            
            if credit['ClientRemaining'] < 25 or credit['UserRemaining'] < 25:
                printCredit = {"noPrint":False}
            else:
                printCredit = {"noPrint":True}

            print(
                "==> Client: {} - User: {} - Reset {}\n".format(
                    credit['ClientRemaining'],
                    credit['UserRemaining'],
                    USER_RESET
                ),end="",**printCredit
            )

            if not (credit['UserRemaining'] == 0 or \
                    credit['ClientRemaining'] == 0):

                """This block of code is needed for API workaround
                """
                while int(time.time() - lastRequestTime) <= 2:
                    pass

                lastRequestTime = time.time()

            else:
                if credit['UserRemaining'] == 0:
                    KEYWORD = "user"
                elif credit['ClientRemaining'] == 0:
                    KEYWORD = "client"

                raise ImgurLimitError('{} LIMIT EXCEEDED\n'.format(KEYWORD.upper()))

        downloaders[SUBMISSION['TYPE']] (directory,SUBMISSION)

    else:
        raise NoSuitablePost

    return None

def download(submissions):
    """Analyze list of submissions and call the right function
    to download each one, catch errors, update the log files
    """

    subsLenght = len(submissions)
    global lastRequestTime
    lastRequestTime = 0
    downloadedCount = subsLenght
    duplicates = 0

    FAILED_FILE = createLogFile("FAILED")

    for i in range(len(submissions)):
        print(f"\n({i+1}/{subsLenght}) – {submissions[i]['POSTID']} – r/{submissions[i]['SUBREDDIT']}",
              end="")
        print(f" – {submissions[i]['TYPE'].upper()}",end="",noPrint=True)

        details = {**submissions[i], **{"TITLE": nameCorrector(submissions[i]['TITLE'])}}
        directory = GLOBAL.directory / GLOBAL.config["folderpath"].format(**details)

        if isPostExists(details,directory):
            print(f"\n" \
                  f"{details['REDDITOR']}_"
                  f"{details['TITLE']}")
            print("It already exists")
            duplicates += 1
            downloadedCount -= 1
            continue

        try:
            downloadPost(details,directory)
        
        except FileAlreadyExistsError:
            # raise FileAlreadyExistsError
            print("It already exists")
            duplicates += 1
            downloadedCount -= 1

        except ImgurLoginError:
            print(
                "Imgur login failed. \nQuitting the program "\
                "as unexpected errors might occur."
            )
            sys.exit()

        except ImgurLimitError as exception:
            FAILED_FILE.add({int(i+1):[
                "{class_name}: {info}".format(
                    class_name=exception.__class__.__name__,info=str(exception)
                ),
                details
            ]})
            downloadedCount -= 1

        except NotADownloadableLinkError as exception:
            print(
                "{class_name}: {info}".format(
                    class_name=exception.__class__.__name__,info=str(exception)
                )
            )
            FAILED_FILE.add({int(i+1):[
                "{class_name}: {info}".format(
                    class_name=exception.__class__.__name__,info=str(exception)
                ),
                submissions[i]
            ]})
            downloadedCount -= 1

        except NoSuitablePost:
            print("No match found, skipping...")
            downloadedCount -= 1
        
        except Exception as exception:
            raise Exception
            print(
                "{class_name}: {info}".format(
                    class_name=exception.__class__.__name__,info=str(exception)
                )
            )
            FAILED_FILE.add({int(i+1):[
                "{class_name}: {info}".format(
                    class_name=exception.__class__.__name__,info=str(exception)
                ),
                submissions[i]
            ]})
            downloadedCount -= 1

    if duplicates:
        print(f"\nThere {'were' if duplicates > 1 else 'was'} " \
              f"{duplicates} duplicate{'s' if duplicates > 1 else ''}")

    if downloadedCount == 0:
        print("Nothing downloaded :(")

    else:
        print(f"Total of {downloadedCount} " \
              f"link{'s' if downloadedCount > 1 else ''} downloaded!")

def printLogo():
    VanillaPrint(
        f"\nBulk Downloader for Reddit v{__version__}\n" \
        f"Written by Ali PARLAKCI – parlakciali@gmail.com\n\n" \
        f"https://github.com/aliparlakci/bulk-downloader-for-reddit/\n"
    )

def main():

    printLogo()

    arguments = Arguments.parse()
    GLOBAL.arguments = arguments

    if arguments.directory is not None:
        GLOBAL.directory = Path(arguments.directory.strip())
    else:
        GLOBAL.directory = Path(input("\ndownload directory: ").strip())

    if not Path(GLOBAL.defaultConfigDirectory).is_dir():
        os.makedirs(GLOBAL.defaultConfigDirectory)

    if Path("config.json").exists():
        GLOBAL.configDirectory = Path("config.json")
    else:
        GLOBAL.configDirectory = GLOBAL.defaultConfigDirectory  / "config.json"

    GLOBAL.config = Config(GLOBAL.configDirectory).generate()

    if arguments.log is not None:
        logDir = Path(arguments.log)
        download(postFromLog(logDir))
        sys.exit()

    programMode = ProgramMode(arguments).generate()

    try:
        posts = getPosts(programMode)
    except Exception as exc:
        logging.error(sys.exc_info()[0].__name__,
                      exc_info=full_exc_info(sys.exc_info()))
        print(log_stream.getvalue(),noPrint=True)
        print(exc)
        sys.exit()

    if posts is None:
        print("I could not find any posts in that URL")
        sys.exit()

    download(posts)

if __name__ == "__main__":

    log_stream = StringIO()    
    logging.basicConfig(stream=log_stream, level=logging.INFO)

    try:
        VanillaPrint = print
        print = printToFile
        GLOBAL.RUN_TIME = time.time()
        main()

    except KeyboardInterrupt:
        if GLOBAL.directory is None:
            GLOBAL.directory = Path(".\\")
        
    except Exception as exception:
        if GLOBAL.directory is None:
            GLOBAL.directory = Path(".\\")
        logging.error(sys.exc_info()[0].__name__,
                      exc_info=full_exc_info(sys.exc_info()))
        print(log_stream.getvalue())

    #if not GLOBAL.arguments.quit: input("\nPress enter to quit\n")
