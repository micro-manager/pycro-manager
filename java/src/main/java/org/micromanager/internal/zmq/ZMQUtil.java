/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package org.micromanager.internal.zmq;

import java.io.*;
import java.lang.reflect.*;
import java.net.*;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.ShortBuffer;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collection;
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
import java.util.stream.Collectors;
import java.util.stream.Stream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

import mmcorej.org.json.JSONArray;
import mmcorej.org.json.JSONException;
import mmcorej.org.json.JSONObject;


/**
 *
 * @author henrypinkard
 */
public class ZMQUtil {

    private static Collection<ClassLoader> classLoaders_;
    private String[] excludedPaths_;
    private HashMap<String, Set<Class>> packageAPIClasses_ = new HashMap<String, Set<Class>>();


   public final static Set<Class> PRIMITIVES = new HashSet<Class>();
   public final static Map<String, Class<?>> PRIMITIVE_NAME_CLASS_MAP = new HashMap<String, Class<?>>();
   public final static Map<String, Class<?>> PRIMITIVE_ARRAY_NAME_CLASS_MAP = new HashMap<String, Class<?>>();

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
      PRIMITIVE_NAME_CLASS_MAP.put("java.lang.Boolean", Boolean.class);
      PRIMITIVE_NAME_CLASS_MAP.put("byte", byte.class);
      PRIMITIVE_NAME_CLASS_MAP.put("java.lang.Byte", Byte.class);
      PRIMITIVE_NAME_CLASS_MAP.put("short", short.class);
      PRIMITIVE_NAME_CLASS_MAP.put("java.lang.Short", Short.class);
      PRIMITIVE_NAME_CLASS_MAP.put("char", char.class);
      PRIMITIVE_NAME_CLASS_MAP.put("java.lang.Character", Character.class);
      PRIMITIVE_NAME_CLASS_MAP.put("int", int.class);
      PRIMITIVE_NAME_CLASS_MAP.put("java.lang.Integer", Integer.class);
      PRIMITIVE_NAME_CLASS_MAP.put("long", long.class);
      PRIMITIVE_NAME_CLASS_MAP.put("java.lang.Long", Long.class);
      PRIMITIVE_NAME_CLASS_MAP.put("float", float.class);
      PRIMITIVE_NAME_CLASS_MAP.put("java.lang.Float", Float.class);
      PRIMITIVE_NAME_CLASS_MAP.put("double", double.class);
      PRIMITIVE_NAME_CLASS_MAP.put("java.lang.Double", Double.class);

      PRIMITIVE_ARRAY_NAME_CLASS_MAP.put("boolean[]", boolean[].class);
      PRIMITIVE_ARRAY_NAME_CLASS_MAP.put("byte[]", byte[].class);
      PRIMITIVE_ARRAY_NAME_CLASS_MAP.put("short[]", short[].class);
      PRIMITIVE_ARRAY_NAME_CLASS_MAP.put("char[]", char[].class);
      PRIMITIVE_ARRAY_NAME_CLASS_MAP.put("int[]", int[].class);
      PRIMITIVE_ARRAY_NAME_CLASS_MAP.put("long[]", long[].class);
      PRIMITIVE_ARRAY_NAME_CLASS_MAP.put("float[]", float[].class);
      PRIMITIVE_ARRAY_NAME_CLASS_MAP.put("double[]", double[].class);
   }

   public ZMQUtil(Collection<ClassLoader> cl, String[] excludePaths) {
       classLoaders_ = cl;
       excludedPaths_ = excludePaths;
   }

   /**
    * Recursively seek through the directory structure under the specified
    * root and generate a list of files that match the given extension.
    * Just a passthrough to the actual recursive method.
    */
   static ArrayList<String> findPaths(String root, String extension) {
      ArrayList<String> result = new ArrayList<>();
      // Short-circuit if we're called with a non-directory.
      if (!(new File(root).isDirectory())) {
         if (root.endsWith(extension)) {
            result.add(root);
         }
         return result;
      }
      recursiveFindPaths(new File(root), extension, result);
      return result;
   }

   private static void recursiveFindPaths(File root, String extension,
                                          ArrayList<String> result) {
      File[] items = root.listFiles();
      for (File item : items) {
         if (item.getAbsolutePath().endsWith(extension)) {
            result.add(item.getAbsolutePath());
         }
         else if (item.isDirectory()) {
            recursiveFindPaths(item, extension, result);
         }
      }
   }

   private static final ByteOrder BYTE_ORDER = ByteOrder.nativeOrder();

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
    * @param externalObjects the servers map of its external objects, needed for memory manamgement
    * @param o Object to be serialized
    * @param json JSONObject that will contain the serialized Object can not be
    * @param port Port that the object is being sent out on
    */
   public void serialize(ConcurrentHashMap<String, Object> externalObjects, Object o, JSONObject json, int port) {
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
            externalObjects.put(hash, o);
            json.put("type", "unserialized-object");
            json.put("class", o.getClass().getName());
            json.put("hash-code", hash);
            json.put("port", port);

            ArrayList<Class> apiInterfaces = new ArrayList<>();
            if (o.getClass().equals(Class.class)) {
               //return the class itself, e.g. to call static methods
               for (Class c : ((Class) o).getInterfaces()) {
                  apiInterfaces.add(c);
               }
               apiInterfaces.add((Class) o);
            } else {
               //Return all interfaces and superclasses interfaces
               Class clazz = o.getClass();
               do {
                  apiInterfaces.add(clazz);
                  for (Class inter : clazz.getInterfaces()) {
                     apiInterfaces.add(inter);
                     recursiveAddInterfaces(apiInterfaces, inter);
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

   private void recursiveAddInterfaces(ArrayList<Class> apiInterfaces, Class inter) {
      for (Class extendedInterface : inter.getInterfaces()) {
         apiInterfaces.add(extendedInterface);
         recursiveAddInterfaces(apiInterfaces, extendedInterface);
      }
   }

   /**
    * Convert array of primitives to a String
    *
    * @param array
    * @return
    */
   public static byte[] encodeArray(Object array) {
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
      return byteArray;
   }

   public static Object decodeArray(byte[] byteArray, Class arrayClass) {
      if (arrayClass.equals(byte[].class)) {
         return byteArray;
      } else if (arrayClass.equals(short[].class)) {
         short[] shorts = new short[byteArray.length / 2];
         ByteBuffer.wrap(byteArray).order(ByteOrder.nativeOrder()).asShortBuffer().get(shorts);
         return shorts;
      } else if (arrayClass.equals(int[].class)) {
         int[] ints = new int[byteArray.length / 4];
         ByteBuffer.wrap(byteArray).order(ByteOrder.nativeOrder()).asIntBuffer().get(ints);
         return ints;
      } else if (arrayClass.equals(double[].class)) {
         double[] doubles = new double[byteArray.length / 8];
         ByteBuffer.wrap(byteArray).order(ByteOrder.nativeOrder()).asDoubleBuffer().get(doubles);
         return doubles;
      } else if (arrayClass.equals(float[].class)) {
         float[] floats = new float[byteArray.length / 4];
         ByteBuffer.wrap(byteArray).order(ByteOrder.nativeOrder()).asFloatBuffer().get(floats);
         return floats;
      }
      throw new RuntimeException("unknown array type");
   }

   public static JSONArray parseConstructors(String classpath, Function<Class, Object> classMapper)
           throws JSONException, ClassNotFoundException {
      JSONArray methodArray = new JSONArray();

      Class clazz = loadClass(classpath);

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
            methJSON.put("return-type", method.getReturnType().getTypeName());
            JSONArray args = new JSONArray();
            for (Class arg : method.getParameterTypes()) {
               args.put(arg.getTypeName());
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

   public static Collection<String> getPackagesFromJars(URLClassLoader cl) {
      HashSet<String> packages = new HashSet<String>();
      for (URL u : cl.getURLs()) {
         try {
         ZipInputStream zip = new ZipInputStream(new FileInputStream(URLDecoder.decode(u.getFile(), "UTF-8")));
            for (ZipEntry entry = zip.getNextEntry(); entry != null; entry = zip.getNextEntry()) {
               if (!entry.isDirectory() && entry.getName().endsWith(".class") && !entry.getName().contains("$")) {
                  // This ZipEntry represents a class. Now, what class does it represent?
                  String className = entry.getName().replace('/', '.');
                  className = className.substring(0, className.length() - 6); // including ".class"
                  try {
                     Class clazz = loadClass(className);
                     try {
                        if (clazz.getPackage() != null) {
                           packages.add(clazz.getPackage().getName());
                        }
                     } catch (Exception sdf) {
                     }
                  } catch (IllegalAccessError e) {
                      //Don't know why this happens but it doesnt seem to matter
                  }
               }
            }
         } catch (Exception e) {
//            e.printStackTrace();
            continue;
         }
      }
      return packages;
   }

   public static Set<String> getPackages() {

      Set<String> packages = new HashSet<String>();
      Package[] p = Package.getPackages();

      for (Package pa : p) {
         packages.add(pa.getName());
      }
      return packages;
   }

   protected static Class loadClass(String path) {
      for (ClassLoader cl : classLoaders_) {
         try {
            return cl.loadClass(path);
         } catch (ClassNotFoundException e) {
            //On to the next one
         } catch (NoClassDefFoundError e) {
            //On to the next one
         } catch (UnsupportedClassVersionError e) {
            System.err.println(path + e.getMessage());
         }

      }
      throw new RuntimeException("Class not found on any classloaders");
   }

   public Set<Class> getPackageClasses(String packageName) throws UnsupportedEncodingException {
        if (packageAPIClasses_.containsKey(packageName)) {
            return packageAPIClasses_.get(packageName);
        }

       Set<Class> packageClasses = new HashSet<Class>();
        if (packageName.contains("java.")) {
           //java classes are different for some reason
           //Aparently you can't find java classes in a package without a third party library
        } else {
           for (ClassLoader classLoader : classLoaders_) {
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
                    packageClasses.addAll(getClassesFromJarFile(directory));
                 } else {
                    packageClasses.addAll(getClassesFromDirectory(packageName, directory));
                 }
              }
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
            for (String exclude : excludedPaths_) {
                if (t.getPackage().getName().contains(exclude)) {
                    return false;
                }
            }
            return true;
         }
      }).collect(Collectors.toSet());

      packageAPIClasses_.put(packageName, classSet);
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
                  ex.printStackTrace();
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
               ex.printStackTrace();
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
      if (argClass.equals(boolean.class) || argClass.equals(Boolean.class)) {
         return primitive;
      } else if (argClass.equals(char.class) || argClass.equals(Character.class)) {
         return (char) ((Number) primitive).intValue();
      } else if (argClass.equals(byte.class) || argClass.equals(Byte.class)) {
         return ((Number) primitive).byteValue();
      } else if (argClass.equals(short.class) || argClass.equals(Short.class)) {
         return ((Number) primitive).shortValue();
      } else if (argClass.equals(int.class) || argClass.equals(Integer.class)) {
         return ((Number) primitive).intValue();
      } else if (argClass.equals(long.class) || argClass.equals(Long.class)) {
         return ((Number) primitive).longValue();
      } else if (argClass.equals(float.class) || argClass.equals(Float.class)) {
         return ((Number) primitive).floatValue();
      } else if (argClass.equals(double.class) || argClass.equals(Double.class)) {
         return ((Number) primitive).doubleValue();
      } else {
         throw new RuntimeException("Unknown class");
      }
   }

   public static Object convertToPrimitiveArray(byte[] bytes, Object clazz) {
      if (clazz.equals(byte[].class)) {
         return bytes;
      }  else if (clazz.equals(short[].class)) {
         short[] shorts = new short[bytes.length / 2];
         ByteBuffer.wrap(bytes).asShortBuffer().get(shorts);
         return shorts;
      } else if (clazz.equals(float[].class)) {
         float[] floats = new float[bytes.length / 4];
         ByteBuffer.wrap(bytes).asFloatBuffer().get(floats);
         return floats;
      } else if (clazz.equals(double[].class)) {
         double[] doubles = new double[bytes.length / 8];
         ByteBuffer.wrap(bytes).asDoubleBuffer().get(doubles);
         return doubles;
      } else if (clazz.equals(int[].class)) {
         int[] ints = new int[bytes.length / 4];
         ByteBuffer.wrap(bytes).asIntBuffer().get(ints);
         return ints;
      } else if (clazz.equals(boolean[].class)) {
         // TODO: boolean array deserialzation
         throw new RuntimeException("Not sure how to handle booleans yet");
      } else if (clazz.equals(char[].class)) {
         char[] chars = new char[bytes.length / 2];
         ByteBuffer.wrap(bytes).asCharBuffer().get(chars);
         return chars;
      } else if (clazz.equals(long[].class)) {
         long[] longs = new long[bytes.length / 8];
         ByteBuffer.wrap(bytes).asLongBuffer().get(longs);
         return longs;
      }
      throw new RuntimeException("unknown type " + clazz.toString());
   }

}
