import syssys.path.append('..')import osimport shutilimport subprocessdef copy(src, dst):    if os.path.isfile(src):        shutil.copyfile(src, dst)    else:        shutil.copytree(src, dst)REMOVE_EXTENSIONS = ['txtc', 'pyc', 'txto', 'pyo']REMOVE_FILES = ['w9xpopen.exe']for root, sub, files in os.walk('./dist'):    for file in files:        path = os.path.join(root, file)        if file in REMOVE_FILES:            os.remove(path)        else:            for ext in REMOVE_EXTENSIONS:                if file.endswith(ext):                    os.remove(path)                    break    def get_hg_rev():    pipe = subprocess.Popen(        ["hg", "log", "-l", "1", "--template", "{node}"],        stdout=subprocess.PIPE, shell = True)    return pipe.stdout.read()[:12]filename = 'pyspades-map_editor-%s.zip' % get_hg_rev()try:    os.remove(filename)except OSError:    passtry:    subprocess.check_call(['7z', 'a', filename, 'dist'])except WindowsError:    print '7zip failed - do you have the 7zip directory in PATH?'