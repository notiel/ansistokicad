import hfsstokicad
import unittest
import os


class HFSSConvertionTest(unittest.TestCase):

    def testAllData(self):
        res = dict()
        print("here")
        for filename in os.listdir("data"):
            if os.path.splitext(filename)[1].lower() in ['.hfss', '.aedt']:
                print(filename)
                res[filename] = hfsstokicad.main(os.path.join("data", filename))
                if res[filename]:
                    os.remove(os.path.join("data", os.path.splitext(filename)[0] + '.kicad_mod'))
                    os.remove(os.path.join("data", os.path.splitext(filename)[0] + '_inverted.kicad_mod'))
                self.assertTrue(res[filename])


if __name__ == '__main__':
    unittest.main()
