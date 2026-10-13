"""Reject extra or changed role membership privilege after recovery."""
import copy, unittest
from complete_db_restore import verify_membership_binding,RestoreStop
class MembershipTests(unittest.TestCase):
    def fixture(self):
        roles=[{'oid':1,'rolname':'reader'},{'oid':2,'rolname':'worker'},{'oid':3,'rolname':'owner'}]
        rows=[{'roleid':1,'member':2,'grantor':3,'admin_option':False,'inherit_option':True,'set_option':True}]
        actual=[{'role':'reader','member':'worker','grantor':'owner','admin_option':False,'inherit_option':True,'set_option':True}]
        return roles,rows,actual
    def test_exact_privileges_and_principals(self):
        self.assertEqual(verify_membership_binding(*self.fixture()),1)
    def test_extra_membership_is_not_accepted(self):
        roles,rows,actual=self.fixture();actual.append(dict(actual[0],member='owner'))
        with self.assertRaises(RestoreStop):verify_membership_binding(roles,rows,actual)
    def test_changed_privilege_or_grantor_is_not_accepted(self):
        for key,value in [('admin_option',True),('inherit_option',False),('set_option',False),('grantor','worker')]:
            roles,rows,actual=self.fixture();actual[0][key]=value
            with self.subTest(key=key),self.assertRaises(RestoreStop):verify_membership_binding(roles,rows,actual)
    def test_missing_membership_is_not_accepted(self):
        roles,rows,_=self.fixture()
        with self.assertRaises(RestoreStop):verify_membership_binding(roles,rows,[])
if __name__=='__main__':unittest.main()
