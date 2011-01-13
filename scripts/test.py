#!/usr/bin/env python

import os, sys, shutil, subprocess

extra_bam_flags = ""
src_path = "tests"
output_path = "test_output"

in_unittest_bloc = 0
failed_tests = []

tests = []
verbose = False

for v in sys.argv:
	if v == "-v":
		verbose = True

bam = "../../bam"
if os.name == 'nt':
	bam = "..\\..\\bam"

if len(sys.argv) > 1:
	tests = sys.argv[1:]

def copytree(src, dst):
	names = os.listdir(src)
	os.mkdir(dst)
	for name in names:
		if name[0] == '.':
			continue
		srcname = os.path.join(src, name)
		dstname = os.path.join(dst, name)
		
		try:
			if os.path.isdir(srcname):
				copytree(srcname, dstname)
			else:
				shutil.copy2(srcname, dstname)
		except (IOError, os.error), why:
			print "Can't copy %s to %s: %s" % (`srcname`, `dstname`, str(why))


def run_bam(testname, flags):
	global output_path
	olddir = os.getcwd()
	os.chdir(output_path+"/"+testname)
	
	p = subprocess.Popen(bam+" "+flags, stdout=subprocess.PIPE, shell=True, stderr=subprocess.STDOUT)
	report = p.stdout.readlines()
	p.wait()
	ret = p.returncode
	os.chdir(olddir)
	
	return (ret, report)
	

def test(name, moreflags="", should_fail=0):
	global output_path, failed_tests, tests

	if len(tests) and not name in tests:
		return

	olddir = os.getcwd()
	os.chdir(output_path+"/"+name)
	cmdline = bam+" -t -v "+extra_bam_flags+" " + moreflags
	
	print name + ":",
	p = subprocess.Popen(cmdline, stdout=subprocess.PIPE, shell=True, stderr=subprocess.STDOUT)
	report = p.stdout.readlines()
	p.wait()
	ret = p.returncode
	
	os.chdir(olddir)
	
	if (should_fail and not ret) or (not should_fail and ret):
		print " FAILED!"
		for l in report:
			print "\t", l,
		failed_tests += [name + "(returned %d)" % ret]
	else:
		print " ok"

def difftest(name, flags1, flags2):
	global failed_tests
	if len(tests) and not name in tests:
		return
	testname = "difftest: %s '%s' vs '%s': "%(name, flags1, flags2)
	print testname,
	ret1, report1 = run_bam(name, flags1)
	ret2, report2 = run_bam(name, flags2)
	
	if ret1:
		print "FAILED! '%s' returned %d" %(flags1, ret1)
		failed_tests += [testname]
		return
	
	if ret2:
		print "FAILED! '%s' returned %d" %(flags2, ret2)
		failed_tests += [testname]
		return
	
	if len(report1) != len(report2):
		print "FAILED! %d lines vs %d lines" % (len(report1), len(report2))
		failed_tests += [testname]
		return
	
	failed = 0
	for i in xrange(0, len(report1)):
		if report1[i] != report2[i]:
			if not failed:
				print "FAILED!"
			print "1:", report1[i].strip()
			print "2:", report2[i].strip()
			failed += 1
			
	if failed:
		failed_tests += [testname]
	else:
		print "ok"

class Test:
	def __init__(self):
		self.line = ""
		self.catch = None
		self.find = None
		self.err = 0 # expect 0 per default

        def is_wrong_error_code(self, code):
        	return self.err != code

        def is_catch_enable(self):
        	return self.catch != None

        def is_catch_equal(self, catch):
        	return self.catch == catch

        def is_find_enable(self):
        	return self.find != None

        def is_find_in_line(self, line):
                return self.find in line
        
def unittests():
	global failed_tests
        
        baseFile = file('src/base.lua')
	tests = get_unittests_from_file(baseFile)
        baseFile.close()
	
	olddir = os.getcwd()
	os.chdir(output_path+"/unit")
	
	for test in tests:
                make_bam_file(test)

		print  "%s:"%(test.line),

                return_code, report_lines = run_bam_on_unittest()
		
		failed = False
                test_succeeded, error_string = error_code_test(test, return_code)
                if not test_succeeded:
                        failed = True
                        print error_string

		
		if test.is_catch_enable():
                        test_succeeded, error_string = catch_test(test, report_lines)
                        if not test_succeeded:
                                failed = True
                                print error_string
		
		if test.is_find_enable():
			test_succeeded, error_string = find_test(test, report_lines)
                        if not test_succeeded:
                                failed = True
                                print error_string

		if failed or verbose:
			if failed:
				failed_tests += [test.line]
			else:
				print "",
			for line in report_lines:
				print "\t", line.rstrip()
		else:
			print "ok"
			

	os.chdir(olddir)

def get_unittests_from_file(file):
        tests = []
	for line in file:
                if is_not_in_unittest_bloc():
			if is_start_unittest_line(line):
                        	enable_unittest_bloc()
		else:
			if is_end_unittest_line(line):
				disable_unittest_bloc()
                        else:
                                test = parse_unittest_line(line)
                                tests += [test]
	return tests

def is_in_unittest_bloc():
        global in_unittest_bloc
	return in_unittest_bloc == 1

def is_not_in_unittest_bloc():
	return not is_in_unittest_bloc()

def is_start_unittest_line(line):
	return "@UNITTESTS" in line

def is_end_unittest_line(line):
	return "@END" in line

def enable_unittest_bloc():
        global in_unittest_bloc
        in_unittest_bloc = 1

def disable_unittest_bloc():
        global in_unittest_bloc
        in_unittest_bloc = 0

def parse_unittest_line(line):
        test = Test()
        args, cmdline = line.split(":", 1)
        test.line = cmdline.strip()
        args = args.split(";")
        for arg in args:
                arg,value = arg.split("=")
                arg = arg.strip()
                value = value.strip()
                if arg.lower() == "err":
                        test.err = int(value)
                elif arg.lower() == "catch":
                	test.catch = value[1:-1]
                elif arg.lower() == "find":
                	test.find = value[1:-1]
        return test

def make_bam_file(test):
        f = file("bam.lua", "w")
        if test.catch != None:
                print >>f, "print(\"CATCH:\", %s)"%(test.line)
	else:
		print >>f, test.line

        print >>f, 'DefaultTarget(PseudoTarget("Test"))'
        f.close()

def run_bam_on_unittest():
        p = subprocess.Popen(
                bam + " --dry",
                stdout = subprocess.PIPE,
                shell = True,
                stderr = subprocess.STDOUT)
	p.wait()

        return p.returncode, p.stdout.readlines()

def error_code_test(test, return_code):
        if test.is_wrong_error_code(return_code):
                return False, "FAILED! error %d != %d" % (test.err, return_code)

        return True, ""

def catch_test(test, lines):
        found = False
	for line in lines:
		splited_line = line.split("CATCH:", 1)
		if len(splited_line) == 2:
			catched = splited_line[1].strip()
			if test.is_catch_equal(catched):
				found = True
               		else:
				error_string = "FAILED! catch '%s' != '%s'" % (test.catch, catched)

	if not found:
		return False, error_string

        return True, ""

def find_test(test, lines):
        found = False
        for line in lines:
                if test.is_find_in_line(line):
                        found = True

		if not found:
			return False, "FAILED! could not find '%s' in output" % (test.find)

        return True, ""

# clean
shutil.rmtree(output_path, True)
# copy tree
copytree("tests", output_path)
os.mkdir(os.path.join(output_path, "unit"))

# run smaller unit tests
if len(tests) == 0:
	unittests()

# run bigger test cases
test("cyclic")
difftest("cyclic", "--debug-nodes", "--debug-nodes -n")
test("include_paths")
difftest("include_paths", "--debug-nodes", "--debug-nodes -n")
test("dot.in.dir")
difftest("dot.in.dir", "--debug-nodes", "--debug-nodes -n")

test("retval", "", 1)
test("multi_target", "SHOULD_NOT_EXIST", 1)
test("multi_target", "CORRECT_ONE")
test("collect_wrong", "", 1)
test("locked", "", 1)
test("cxx_dep")
test("deps", "", 1)
test("collect_recurse")
test("sharedlib")
test("deadlock")
test("addorder")

if len(failed_tests):
	print "FAILED TESTS:"
	for t in failed_tests:
		print "\t"+t
else:
	print "ALL TESTS PASSED!"

