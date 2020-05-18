/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package org.micromanager.internal.zmq;

import java.io.File;
import java.io.FilenameFilter;
import java.io.IOException;
import java.io.UnsupportedEncodingException;
import java.lang.reflect.*;
import java.net.URI;
import java.net.URISyntaxException;
import java.net.URL;
import java.net.URLDecoder;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Base64;
import java.util.Collection;
import java.util.Collections;
import java.util.Enumeration;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Consumer;
import java.util.function.Function;
import java.util.function.Predicate;
import java.util.jar.JarEntry;
import java.util.jar.JarFile;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import mmcorej.org.json.JSONArray;
import mmcorej.org.json.JSONException;
import mmcorej.org.json.JSONObject;

/**
 *
 * @author henrypinkard
 */
public class ZMQUtil {

    private ClassLoader classLoader_;
    private String[] excludedPaths_;
    private HashMap<String, Set<Class>> packageAPIClasses_ = new HashMap<String, Set<Class>>();

   //TODO: associtate entries in here with a prticular client
   //map of objects that exist in some client of the server
   protected final static ConcurrentHashMap<String, Object> EXTERNAL_OBJECTS
           = new ConcurrentHashMap<String, Object>();

   public final static Set<Class> PRIMITIVES = new HashSet<Class>();
   public final static Map<String, Class<?>> PRIMITIVE_NAME_CLASS_MAP = new HashMap<String, Class<?>>();

   static {
      PRIMITIVES.add(Boolean.class);
      PRIMITIVES.add(Byte.class);
      PRIMITIVES.add(Short.class);
      PRIMITIVES.add(Character.class);
      PRIMITIVES.add(Integer.class);
      PRIMITIVES.add(Long.class);
      PRIMITIVES.add(Float.class);
      PRIMITIVES.add(Double.class);

      PRIMITIVE_NAME_CLASS_MAP.put("boolean", boolean.class);
      PRIMITIVE_NAME_CLASS_MAP.put("byte", byte.class);
      PRIMITIVE_NAME_CLASS_MAP.put("short", short.class);
      PRIMITIVE_NAME_CLASS_MAP.put("char", char.class);
      PRIMITIVE_NAME_CLASS_MAP.put("int", int.class);
      PRIMITIVE_NAME_CLASS_MAP.put("long", long.class);
      PRIMITIVE_NAME_CLASS_MAP.put("float", float.class);
      PRIMITIVE_NAME_CLASS_MAP.put("double", double.class);
   }

   public ZMQUtil(ClassLoader cl, String[] excludePaths) {
       classLoader_ = cl;
       excludedPaths_ = excludePaths;
   }

   private static final ByteOrder BYTE_ORDER = ByteOrder.BIG_ENDIAN;

   protected static Object deserialize(byte[] message, Function<JSONObject, ?> deserializationFn) {
      try {
         String s = new String(message);
         JSONObject json = new JSONObject(s);
         String type = json.getString("type");
         if (type.equals("object")) {
            Object result = deserializationFn.apply(json.getJSONObject("value"));
            return result;
         }
         throw new RuntimeException("Problem decoding message");
      } catch (JSONException ex) {
         throw new RuntimeException("Problem turning message into JSON. ");
      }
   }

   /**
    * Convert objects that will be serialized into JSON. Used for objects that
    * will pass out and never need to be returned
    *
    */
   public static JSONObject toJSON(Object o) {
      JSONObject json = new JSONObject();
      try {
         if (o instanceof Exception) {
            json.put("type", "exception");
            Throwable root = ((Exception) o).getCause() == null
                    ? ((Exception) o) : ((Exception) o).getCause();
            String s = root.toString() + "\n";
            for (StackTraceElement el : root.getStackTrace()) {
               s += el.toString() + "\n";
            }
            json.put("value", s);
         } else if (o instanceof String) {
            json.put("type", "string");
            json.put("value", o);
         } else if (o == null) {
            json.put("type", "none");
         } else if (PRIMITIVES.contains(o.getClass())) {
            json.put("type", "primitive");
            json.put("value", o);
         } else if (o.getClass().equals(JSONObject.class)) {
            json.put("type", "object");
            json.put("class", "JSONObject");
            json.put("value", o.toString());
         } else if (o.getClass().equals(byte[].class)) {
            json.put("type", "byte-array");
            json.put("value", encodeArray(o));
         } else if (o.getClass().equals(short[].class)) {
            json.put("type", "short-array");
            json.put("value", encodeArray(o));
         } else if (o.getClass().equals(double[].class)) {
            json.put("type", "double-array");
            json.put("value", encodeArray(o));
         } else if (o.getClass().equals(int[].class)) {
            json.put("type", "int-array");
            json.put("value", encodeArray(o));
         } else if (o.getClass().equals(float[].class)) {
            json.put("type", "float-array");
            json.put("value", encodeArray(o));
         } else {
            return null;
         }
      } catch (JSONException e) {
         throw new RuntimeException(e);
      }
      return json;
   }

   /**
    * This version serializes primitves, converts lists to JSONArrays, and sends
    * out pointers to Objects
    *
    * @param o Object to be serialized
    * @param json JSONObject that will contain the serialized Object can not be
    * null
    */
   public void serialize(Object o, JSONObject json, int port) {
      try {
         JSONObject converted = toJSON(o);
         if (converted != null) {
            //Can be driectly converted into a serialized object (i.e. primitive)--copy into
            converted.keys().forEachRemaining(new Consumer<String>() {
               @Override
               public void accept(String t) {
                  try {
                     json.put(t, converted.get(t));
                  } catch (JSONException ex) {
                     throw new RuntimeException(ex); //Wont happen
                  }
               }
            });
         } else {
            //Don't serialize the object, but rather send out its name so that python side
            //can construct a shadow version of it
            //Keep track of which objects have been sent out, so that garbage collection can be synchronized between
            //the two languages
            String hash = Integer.toHexString(System.identityHashCode(o));
            //Add a random UUID to account for the fact that there may be multiple
            //pythons shadows of the same object
            hash += UUID.randomUUID();
            EXTERNAL_OBJECTS.put(hash, o);
            json.put("type", "unserialized-object");
            json.put("class", o.getClass().getName());
            json.put("hash-code", hash);
            json.put("port", port);

            ArrayList<Class> apiInterfaces = new ArrayList<>();
            if (o.getClass().getName().startsWith("java")) {
               //Java classes
               for (Class c : o.getClass().getInterfaces()) {
                  apiInterfaces.add(c);
               }
               apiInterfaces.add(o.getClass());
            } else {
               //Non Java classes. Check to make sure only exposing things we mean to

               Set<String> packageNames = new HashSet<String>();
               //Search through all superclasses and interfaces
               Class clazz = o.getClass();
               do {
                  apiInterfaces.add(clazz);
                  for (Class inter : clazz.getInterfaces()) {
                     apiInterfaces.add(inter);
                  }
                  clazz = clazz.getSuperclass();
               } while (clazz != null);
            }

            if (apiInterfaces.isEmpty()) {
               throw new RuntimeException("Couldn't find " + o.getClass().getName()
                       + " on classpath, or this is an internal class that was accidentally exposed");
            }
            //List all API interfaces this class implments in case its passed
            //back as an argument to another function
            JSONArray e = new JSONArray();
            json.put("interfaces", e);
            for (Class c : apiInterfaces) {
               e.put(c.getName());
            }

            //copy in all public fields of the object
            JSONArray f = new JSONArray();
            json.put("fields", f);
            for (Field field : o.getClass().getFields()) {
               int modifiers = field.getModifiers();
               if (Modifier.isPublic(modifiers)) {
                  f.put(field.getName());
               }
            }

            json.put("api", parseAPI(apiInterfaces));
         }
      } catch (JSONException e) {
         throw new RuntimeException(e);
      }
   }

   /**
    * Convert array of primitives to a String
    *
    * @param array
    * @return
    */
   public static String encodeArray(Object array) {
      byte[] byteArray = null;
      if (array instanceof byte[]) {
         byteArray = (byte[]) array;
      } else if (array instanceof short[]) {
         ByteBuffer buffer = ByteBuffer.allocate((((short[]) array)).length * Short.BYTES);
         buffer.order(BYTE_ORDER).asShortBuffer().put((short[]) array);
         byteArray = buffer.array();
      } else if (array instanceof int[]) {
         ByteBuffer buffer = ByteBuffer.allocate((((int[]) array)).length * Integer.BYTES);
         buffer.order(BYTE_ORDER).asIntBuffer().put((int[]) array);
         byteArray = buffer.array();
      } else if (array instanceof double[]) {
         ByteBuffer buffer = ByteBuffer.allocate((((double[]) array)).length * Double.BYTES);
         buffer.order(BYTE_ORDER).asDoubleBuffer().put((double[]) array);
         byteArray = buffer.array();
      } else if (array instanceof float[]) {
         ByteBuffer buffer = ByteBuffer.allocate((((float[]) array)).length * Float.BYTES);
         buffer.order(BYTE_ORDER).asFloatBuffer().put((float[]) array);
         byteArray = buffer.array();
      }
      return Base64.getEncoder().encodeToString(byteArray);
   }

   public static Object decodeArray(String serialized, Class arrayClass) {
      byte[] byteArray = Base64.getDecoder().decode(serialized);
      if (arrayClass.equals(byte[].class)) {
         return byteArray;
      } else if (arrayClass.equals(short[].class)) {
         short[] shorts = new short[byteArray.length / 2];
         ByteBuffer.wrap(byteArray).asShortBuffer().get(shorts);
         return shorts;
      } else if (arrayClass.equals(int[].class)) {
         int[] ints = new int[byteArray.length / 4];
         ByteBuffer.wrap(byteArray).asIntBuffer().get(ints);
         return ints;
      } else if (arrayClass.equals(double[].class)) {
         double[] doubles = new double[byteArray.length / 8];
         ByteBuffer.wrap(byteArray).asDoubleBuffer().get(doubles);
         return doubles;
      } else if (arrayClass.equals(float[].class)) {
         float[] floats = new float[byteArray.length / 4];
         ByteBuffer.wrap(byteArray).asFloatBuffer().get(floats);
         return floats;
      }
      throw new RuntimeException("unknown array type");
   }

   public static JSONArray parseConstructors(String classpath, Function<Class, Object> classMapper)
           throws JSONException, ClassNotFoundException {
      JSONArray methodArray = new JSONArray();
      Class clazz = Class.forName(classpath);

      Constructor[] m = clazz.getConstructors();
      for (Constructor c : m) {
         JSONObject methJSON = new JSONObject();
         methJSON.put("name", c.getName());
         JSONArray args = new JSONArray();
         for (Class arg : c.getParameterTypes()) {
            args.put(arg.getCanonicalName());
         }
         methJSON.put("arguments", args);
         methodArray.put(methJSON);
      }
      // add in 0 argmunet "constructors" for interfaces that get mapped to an existing instance of a class
      if (clazz.isInterface()) {
         if (classMapper.apply(clazz) != null) {
            JSONObject methJSON = new JSONObject();
            methJSON.put("name", clazz.getName());
            JSONArray args = new JSONArray();
            methJSON.put("arguments", args);
            methodArray.put(methJSON);
         }
      }

      return methodArray;
   }

   /**
    * Go through all methods of the given class and put them into a big JSON
    * array that describes the API
    *
    * @param apiClasses Classes to be translated into JSON
    * @return Classes translated to JSON
    * @throws JSONException
    */
   private static JSONArray parseAPI(ArrayList<Class> apiClasses) throws JSONException {
      JSONArray methodArray = new JSONArray();
      for (Class clazz : apiClasses) {
         for (Method method : clazz.getDeclaredMethods()) {
            JSONObject methJSON = new JSONObject();
            methJSON.put("name", method.getName());
            methJSON.put("return-type", method.getReturnType().getCanonicalName());
            JSONArray args = new JSONArray();
            for (Class arg : method.getParameterTypes()) {
               args.put(arg.getCanonicalName());
            }
            methJSON.put("arguments", args);
//            JSONArray argNames = new JSONArray();
//            for (Parameter p : method.getParameters()) {
//               argNames.put(p.getName());
//            }
//            methJSON.put("argument-names", argNames);
            methodArray.put(methJSON);
         }
      }
      return methodArray;
   }

   public static Set<String> getPackages(ClassLoader classLoader) {
      Set<String> packages = new HashSet<String>();
      Package[] p = Package.getPackages();
      for (Package pa : p) {
         packages.add(pa.getName());
      }
      return packages;
   }

   public Set<Class> getPackageClasses(String packageName) throws UnsupportedEncodingException {
        if (packageAPIClasses_.containsKey(packageName)) {
            return packageAPIClasses_.get(packageName);
        }

       Set<Class> packageClasses = new HashSet<Class>();
       String path = packageName.replace('.', '/');
       Enumeration<URL> resources;
       try {
           resources = classLoader_.getResources(path);
       } catch (IOException ex) {
           throw new RuntimeException("Invalid package name in ZMQ server: " + path);
       }
       List<File> dirs = new ArrayList<>();
       while (resources.hasMoreElements()) {
           URL resource = resources.nextElement();
           String file = resource.getFile().replaceAll("^file:", "");
           file = (String) URLDecoder.decode(file, "UTF-8");

           dirs.add(new File(file));
       }

       for (File directory : dirs) {
           if (directory.getAbsolutePath().contains(".jar")) {
               packageClasses.addAll(getClassesFromJarFile(directory));
           } else {
               packageClasses.addAll(getClassesFromDirectory(packageName, directory));
           }
       }

      //filter out internal classes
      Stream<Class> clazzStream = packageClasses.stream();
      Set<Class> classSet = clazzStream.filter(new Predicate<Class>() {
         @Override
         public boolean test(Class t) {
            Package p = t.getPackage();
            if (p == null) {
               return true;
            }
            boolean invalid = false;
            for (String exclude : excludedPaths_) {
                if (t.getPackage().getName().contains(exclude)) {
                    return true;
                }
            }
            return false;
         }
      }).collect(Collectors.toSet());

      packageAPIClasses_.put(packageName, packageClasses);
      return packageClasses;
   }


   private static Set<Class> getAPIClasses(ClassLoader classLoader) throws
           URISyntaxException, UnsupportedEncodingException {

      HashSet<Class> apiClasses = new HashSet<Class>();

      //recursively get all names that have org.micromanager, but not internal in the name
      ArrayList<String> mmPackages = new ArrayList<>();
      Package[] p = Package.getPackages();
      for (Package pa : p) {
         //Add all non internal MM classes
//         if (pa.getName().contains("org.micromanager") && !pa.getName().contains("internal")) {
//            mmPackages.add(pa.getName());
//         }
//         //Add all core classes
//         if (pa.getName().contains("mmcorej")) {
//            mmPackages.add(pa.getName());
//         }

         mmPackages.add(pa.getName());
      }

      //TODO: this is for netbeans, delte or split out
      mmPackages.add("org.micromanager.remote");
      mmPackages.add("org.micromanager.magellan.api");
      mmPackages.add("org.micromanager.acqj.api");

      // ClassLoader classLoader = Thread.currentThread().getContextClassLoader();
      for (String packageName : mmPackages) {
         String path = packageName.replace('.', '/');
         Enumeration<URL> resources;
         try {
            resources = classLoader.getResources(path);
         } catch (IOException ex) {
            throw new RuntimeException("Invalid package name in ZMQ server: " + path);
         }
         List<File> dirs = new ArrayList<>();
         while (resources.hasMoreElements()) {
            URL resource = resources.nextElement();
            String file = resource.getFile().replaceAll("^file:", "");
            file = (String) URLDecoder.decode(file, "UTF-8");

            dirs.add(new File(file));
         }

         for (File directory : dirs) {
            if (directory.getAbsolutePath().contains(".jar")) {
               apiClasses.addAll(getClassesFromJarFile(directory));
         } else {
               apiClasses.addAll(getClassesFromDirectory(packageName, directory));
            }
         }
      }

      //filter out internal classes
      Stream<Class> clazzStream = apiClasses.stream();
      Set<Class> classSet = clazzStream.filter(new Predicate<Class>() {
         @Override
         public boolean test(Class t) {
            Package p = t.getPackage();
            if (p == null) {
               return true;
            }
            return !t.getPackage().getName().contains("internal");
         }
      }).collect(Collectors.toSet());
      return classSet;
   }

   private static Collection<Class> getClassesFromJarFile(File directory) {
      List<Class> classes = new ArrayList<Class>();

      try {
         String jarPath = Stream.of(directory.getAbsolutePath().split(File.pathSeparator))
                 .flatMap((String t) -> Stream.of(t.split("!")))
                 .filter((String t) -> t.contains(".jar")).findFirst().get();
         JarFile jarFile = new JarFile(jarPath);
         Enumeration<JarEntry> entries = jarFile.entries();
         while (entries.hasMoreElements()) {
            JarEntry entry = entries.nextElement();
            String name = entry.getName();
            //include classes but not inner classes
            if (name.endsWith(".class") && !name.contains("$")) {
               try {
                  classes.add(Class.forName(name.replace("/", ".").
                          substring(0, name.length() - 6)));
               } catch (ClassNotFoundException ex) {
//                  studio_.logs().logError("Class not found in ZMQ server: " + name);
               }
            }
         }
      } catch (IOException ex) {
         throw new RuntimeException(ex);
      }

      return classes;
   }

   private static Collection<Class> getClassesFromDirectory(String packageName, File directory) {
      List<Class> classes = new ArrayList<Class>();

      // get jar files from top-level directory
      List<File> jarFiles = listFiles(directory, new FilenameFilter() {
         @Override
         public boolean accept(File dir, String name) {
            return name.endsWith(".jar");
         }
      }, false);

      for (File file : jarFiles) {
         classes.addAll(getClassesFromJarFile(file));
      }

      // get all class-files
      List<File> classFiles = listFiles(directory, new FilenameFilter() {
         @Override
         public boolean accept(File dir, String name) {
            return name.endsWith(".class");
         }
      }, true);

      for (File file : classFiles) {
         if (!file.isDirectory()) {
            try {
               classes.add(Class.forName(packageName + '.' + file.getName().
                       substring(0, file.getName().length() - 6)));
            } catch (ClassNotFoundException ex) {
//               studio_.logs().logError("Failed to load class: " + file.getName());
            }
         }
      }
      return classes;
   }

   private static List<File> listFiles(File directory, FilenameFilter filter, boolean recurse) {
      List<File> files = new ArrayList<File>();
      File[] entries = directory.listFiles();

      // Go over entries
      for (File entry : entries) {
         // If there is no filter or the filter accepts the
         // file / directory, add it to the list
         if (filter == null || filter.accept(directory, entry.getName())) {
            files.add(entry);
         }

         // If the file is a directory and the recurse flag
         // is set, recurse into the directory
         if (recurse && entry.isDirectory()) {
            files.addAll(listFiles(entry, filter, recurse));
         }
      }

      // Return collection of files
      return files;
   }

   static Object convertToPrimitiveClass(Object primitive, Class argClass) {
      if (argClass.equals(boolean.class)) {
         return primitive;
      } else if (argClass.equals(char.class)) {
         return (char) ((Number) primitive).intValue();
      } else if (argClass.equals(byte.class)) {
         return ((Number) primitive).byteValue();
      } else if (argClass.equals(short.class)) {
         return ((Number) primitive).shortValue();
      } else if (argClass.equals(int.class)) {
         return ((Number) primitive).intValue();
      } else if (argClass.equals(long.class)) {
         return ((Number) primitive).longValue();
      } else if (argClass.equals(float.class)) {
         return ((Number) primitive).floatValue();
      } else if (argClass.equals(double.class)) {
         return ((Number) primitive).doubleValue();
      } else {
         throw new RuntimeException("Unkown class");
      }
   }
}
