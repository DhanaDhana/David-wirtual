
class Router(object):
   
    def db_for_read(self, model, **hints):
        if model._meta.app_label=='data_collection':
            return 'mongo_db'
        # Returning None is no opinion, defer to other routers or default database
        return None

    def db_for_write(self, model, **hints):
        # print("write>>", model._meta.app_label)
        if model._meta.app_label=='data_collection':
            return 'mongo_db'
        # Returning None is no opinion, defer to other routers or default database
        return None

    # def allow_relation(self, obj1, obj2, **hints):
    #     # Allow relations between two models that are both Django core app models
    #     if obj1._meta.app_label in in ['payment'] and obj2.meta.app_label in in ['payment']:
    #         return True
    #     # If neither object is in a Django core app model (defer to other routers or default database)
    #     elif obj1._meta.app_label not in ['auth', 'admin', 'sessions', 'contenttypes'] or
    #     obj2._meta.app_label not in ['auth', 'admin', 'sessions', 'contenttypes']:
    #         return None
    #     return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == 'mongo_db':
            # Migrate Django core app models if current database is devops
            if app_label=='data_collection':
                return True
                
            else:
                # Non Django core app models should not be migrated if database is devops
                return False
        # Other database should not migrate Django core app models
        elif app_label=='data_collection':
            return False
        # Otherwise no opinion, defer to other routers or default database
        return None




